from __future__ import annotations

import ipaddress
import json
import os
import queue
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from potato_agent.models import (
    AvailabilityStatus,
    EligibilityStatus,
    MeetingSnapshot,
    ResponseStatus,
)
from potato_agent.qwen_proposals import (
    ProposalActor,
    ProposalValidationError,
    RescheduleProposal,
    RescheduleProposalDraft,
    parse_proposal_payload,
    validate_proposal,
)


class ThinkingMode(StrEnum):
    THINK = "think"
    NO_THINK = "no_think"


class LlamaCppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = "http://127.0.0.1:18081"
    model: StrictStr = "potato-qwen-test"
    thinking_mode: ThinkingMode = ThinkingMode.NO_THINK
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    total_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    tool_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    max_tool_calls: int = Field(default=3, ge=0, le=8)
    max_response_bytes: int = Field(default=1_000_000, ge=1024, le=4_000_000)


class LlamaCppError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ReadOnlyMeetingTools(Protocol):
    def get_availability(self, participant_id: str) -> dict[str, Any]: ...

    def get_meeting_constraints(self) -> dict[str, Any]: ...

    def find_common_slots(self, requested_date: date | None) -> dict[str, Any]: ...


class LocalSnapshotReadTools:
    """Local read-only context tools for a single authoritative snapshot."""

    def __init__(self, snapshot: MeetingSnapshot) -> None:
        self._snapshot = snapshot

    def get_availability(self, participant_id: str) -> dict[str, Any]:
        participant = next(
            (p for p in self._snapshot.participants if p.participant_id == participant_id),
            None,
        )
        if participant is None:
            raise LlamaCppError("PARTICIPANT_NOT_FOUND", "Participant is not in this meeting.")
        if participant.response_status != ResponseStatus.ACCEPTED:
            raise LlamaCppError(
                "PARTICIPANT_NOT_ELIGIBLE", "Availability is unavailable for this response state."
            )
        if participant.eligibility_status != EligibilityStatus.ACTIVE:
            raise LlamaCppError(
                "PARTICIPANT_NOT_ELIGIBLE", "Availability is unavailable for this participant."
            )
        submission = self._snapshot.availability_by_participant_id.get(participant_id)
        if submission is None or submission.status == AvailabilityStatus.NOT_SUBMITTED:
            return {
                "participantId": participant_id,
                "status": "NOT_SUBMITTED",
                "slots": [],
                "timeZone": self._snapshot.time_zone,
            }
        return {
            "participantId": participant_id,
            "status": submission.status.value,
            "slots": [
                {
                    "date": slot.date.isoformat(),
                    "startMinute": slot.start_minute,
                    "endMinute": slot.end_minute,
                }
                for slot in submission.slots
            ],
            "timeZone": submission.time_zone,
        }

    def get_meeting_constraints(self) -> dict[str, Any]:
        snapshot = self._snapshot
        return {
            "inputRevision": snapshot.input_revision,
            "title": snapshot.title,
            "activity": snapshot.activity,
            "location": snapshot.location,
            "dates": [item.isoformat() for item in snapshot.dates],
            "excludedDates": [item.isoformat() for item in snapshot.excluded_dates],
            "durationMinutes": snapshot.duration_minutes,
            "minimumAttendeeCount": snapshot.minimum_attendee_count,
            "timeZone": snapshot.time_zone,
            "requiredStartMinutesByDate": {
                day.isoformat(): minute
                for day, minute in snapshot.required_start_minutes_by_date.items()
            },
            "absoluteTimeWindows": [
                {
                    "date": window.date.isoformat(),
                    "startMinute": window.start_minute,
                    "endMinute": window.end_minute,
                }
                for window in snapshot.absolute_time_windows
            ],
        }

    def find_common_slots(self, requested_date: date | None) -> dict[str, Any]:
        snapshot = self._snapshot
        eligible = [
            participant
            for participant in snapshot.participants
            if participant.response_status == ResponseStatus.ACCEPTED
            and participant.eligibility_status.value == "ACTIVE"
        ]
        if any(
            participant.response_status == ResponseStatus.PENDING
            and participant.eligibility_status.value == "ACTIVE"
            for participant in snapshot.participants
        ):
            raise LlamaCppError(
                "WAITING_FOR_INPUT", "RSVP responses are still pending."
            )
        submissions = [
            snapshot.availability_by_participant_id.get(participant.participant_id)
            for participant in eligible
        ]
        if any(
            submission is None or submission.status != AvailabilityStatus.SUBMITTED
            for submission in submissions
        ):
            raise LlamaCppError(
                "WAITING_FOR_INPUT", "Participant availability is not fully submitted."
            )

        per_participant: list[dict[date, list[tuple[int, int]]]] = []
        for submission in submissions:
            assert submission is not None
            intervals_by_date: dict[date, list[tuple[int, int]]] = {}
            for slot in submission.slots:
                intervals_by_date.setdefault(slot.date, []).append(
                    (slot.start_minute, slot.end_minute)
                )
            for slot_date, intervals in intervals_by_date.items():
                merged: list[list[int]] = []
                for start, end in sorted(intervals):
                    if merged and start <= merged[-1][1]:
                        merged[-1][1] = max(merged[-1][1], end)
                    else:
                        merged.append([start, end])
                intervals_by_date[slot_date] = [
                    (start, end) for start, end in merged
                ]
            per_participant.append(intervals_by_date)

        common_slots: list[dict[str, Any]] = []
        candidate_dates = sorted(
            day
            for day in snapshot.dates
            if day not in snapshot.excluded_dates
            and (requested_date is None or day == requested_date)
        )
        windows_by_date: dict[date, list[tuple[int, int]]] = {}
        for window in snapshot.absolute_time_windows:
            windows_by_date.setdefault(window.date, []).append(
                (window.start_minute, window.end_minute)
            )
        for slot_date in candidate_dates:
            starts = snapshot.required_start_minutes_by_date.get(slot_date)
            common = per_participant[0].get(slot_date, [])
            for participant_intervals in per_participant[1:]:
                intersections = []
                for start_a, end_a in common:
                    for start_b, end_b in participant_intervals.get(slot_date, []):
                        start = max(start_a, start_b)
                        end = min(end_a, end_b)
                        if start < end:
                            intersections.append((start, end))
                common = intersections
            if starts is not None:
                common = [
                    (start, end)
                    for start, end in common
                    if start <= starts and starts + snapshot.duration_minutes <= end
                ]
            allowed_windows = windows_by_date.get(slot_date, [])
            for start, end in common:
                if allowed_windows:
                    for window_start, window_end in allowed_windows:
                        intersection_start = max(start, window_start)
                        intersection_end = min(end, window_end)
                        if intersection_start < intersection_end:
                            common_slots.append(
                                {
                                    "date": slot_date.isoformat(),
                                    "startMinute": intersection_start,
                                    "endMinute": intersection_end,
                                }
                            )
                else:
                    common_slots.append(
                        {
                            "date": slot_date.isoformat(),
                            "startMinute": start,
                            "endMinute": end,
                        }
                    )
        return {
            "timeZone": snapshot.time_zone,
            "durationMinutes": snapshot.duration_minutes,
            "commonAvailabilityWindows": common_slots[:20],
        }


class ReadOnlyToolDispatcher:
    MAX_ARGUMENT_BYTES = 16_384

    def __init__(self, tools: ReadOnlyMeetingTools) -> None:
        self._tools = tools
        self.call_count = 0

    @staticmethod
    def definitions() -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_availability",
                    "description": "Read one accepted participant's submitted availability by authoritative ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"participant_id": {"type": "string"}},
                        "required": ["participant_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_meeting_constraints",
                    "description": "Read the current meeting constraints and input revision.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_common_slots",
                    "description": "Read common availability windows; this does not create or approve candidates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": ["string", "null"], "format": "date"}
                        },
                        "required": ["date"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def invoke(
        self,
        name: str,
        arguments_json: str,
        *,
        max_calls: int,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        if name not in {
            "get_availability",
            "get_meeting_constraints",
            "find_common_slots",
        }:
            raise LlamaCppError("TOOL_NOT_ALLOWED", "The model requested a disallowed tool.")
        if self.call_count >= max_calls:
            raise LlamaCppError("TOOL_CALL_LIMIT", "The read-only tool call limit was exceeded.")
        if len(arguments_json.encode("utf-8")) > self.MAX_ARGUMENT_BYTES:
            raise LlamaCppError("INVALID_TOOL_ARGUMENTS", "Tool arguments exceeded the size limit.")
        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError as exc:
            raise LlamaCppError("INVALID_TOOL_ARGUMENTS", "Tool arguments were not valid JSON.") from exc
        if not isinstance(arguments, dict):
            raise LlamaCppError("INVALID_TOOL_ARGUMENTS", "Tool arguments must be a JSON object.")

        def execute() -> dict[str, Any]:
            if name == "get_availability":
                if set(arguments) != {"participant_id"} or not isinstance(
                    arguments["participant_id"], str
                ):
                    raise LlamaCppError(
                        "INVALID_TOOL_ARGUMENTS", "get_availability requires participant_id."
                    )
                return self._tools.get_availability(arguments["participant_id"])
            elif name == "get_meeting_constraints":
                if arguments:
                    raise LlamaCppError(
                        "INVALID_TOOL_ARGUMENTS", "get_meeting_constraints takes no arguments."
                    )
                return self._tools.get_meeting_constraints()
            else:
                if set(arguments) != {"date"} or (
                    arguments["date"] is not None
                    and not isinstance(arguments["date"], str)
                ):
                    raise LlamaCppError(
                        "INVALID_TOOL_ARGUMENTS", "find_common_slots accepts an optional ISO date."
                    )
                try:
                    requested_date = (
                        None
                        if arguments["date"] is None
                        else date.fromisoformat(arguments["date"])
                    )
                except ValueError as exc:
                    raise LlamaCppError(
                        "INVALID_TOOL_ARGUMENTS", "find_common_slots date must be ISO format."
                    ) from exc
                return self._tools.find_common_slots(requested_date)

        if timeout_seconds <= 0:
            raise LlamaCppError(
                "TOOL_TIMEOUT", "The read-only meeting tool exceeded its time limit."
            )
        result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

        def run_read_only_tool() -> None:
            try:
                result_queue.put((True, execute()))
            except Exception as exc:
                result_queue.put((False, exc))

        worker = threading.Thread(target=run_read_only_tool, daemon=True)
        worker.start()
        try:
            succeeded, result = result_queue.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise LlamaCppError(
                "TOOL_TIMEOUT", "The read-only meeting tool exceeded its time limit."
            ) from exc
        if not succeeded:
            if isinstance(result, LlamaCppError):
                raise result
            raise LlamaCppError(
                "READ_ONLY_TOOL_FAILED", "A read-only meeting tool failed."
            ) from result
        self.call_count += 1
        return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, _req, _fp, _code, _msg, _headers, _newurl):
        return None


class LlamaCppClient:
    def __init__(self, config: LlamaCppConfig | None = None) -> None:
        if config is None:
            config = LlamaCppConfig(
                base_url=os.environ.get(
                    "POTATO_LLAMA_CPP_URL", "http://127.0.0.1:18081"
                ),
                model=os.environ.get("POTATO_QWEN_MODEL", "potato-qwen-test"),
                thinking_mode=os.environ.get(
                    "POTATO_QWEN_THINKING_MODE", ThinkingMode.NO_THINK.value
                ),
            )
        self.config = config
        self._base_url = self._validate_local_url(config.base_url)
        self._opener = urllib.request.build_opener(_NoRedirect)

    @staticmethod
    def _validate_local_url(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("llama.cpp endpoint must be an HTTP(S) loopback URL.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("llama.cpp endpoint must not contain credentials or query values.")
        if parsed.path not in ("", "/"):
            raise ValueError("llama.cpp base URL must not include an API path.")
        if parsed.port == 8080:
            raise ValueError("The production Qwen endpoint on port 8080 is not allowed.")
        try:
            addresses = {
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(
                    parsed.hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                )
            }
        except (OSError, ValueError) as exc:
            raise ValueError("llama.cpp endpoint host could not be resolved locally.") from exc
        if not addresses or any(not address.is_loopback for address in addresses):
            raise ValueError("Only a loopback llama.cpp endpoint is allowed.")
        return url.rstrip("/")

    def _request(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if path not in ("/health", "/props", "/v1/models", "/v1/chat/completions"):
            raise ValueError("Unsupported llama.cpp endpoint path.")
        url = f"{self._base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="GET" if body is None else "POST",
        )
        try:
            with self._opener.open(
                request,
                timeout=timeout_seconds or self.config.request_timeout_seconds,
            ) as response:
                raw = response.read(self.config.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise LlamaCppError(
                "LOCAL_INFERENCE_FAILED",
                f"llama.cpp returned HTTP {exc.code}.",
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            code = "LOCAL_INFERENCE_TIMEOUT" if isinstance(exc, TimeoutError) else "LLAMA_UNAVAILABLE"
            raise LlamaCppError(
                code, "The configured local llama.cpp endpoint is unavailable."
            ) from exc
        if len(raw) > self.config.max_response_bytes:
            raise LlamaCppError("RESPONSE_TOO_LARGE", "llama.cpp response exceeded the size limit.")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LlamaCppError(
                "INVALID_LOCAL_RESPONSE", "llama.cpp did not return valid JSON."
            ) from exc
        if not isinstance(decoded, dict):
            raise LlamaCppError(
                "INVALID_LOCAL_RESPONSE", "llama.cpp response must be a JSON object."
            )
        return decoded

    def probe(self) -> dict[str, Any]:
        """Read health and model metadata only; never starts or reconfigures a server."""
        try:
            health = self._request("/health")
            properties = self._request("/props")
            model_response = self._request("/v1/models")
            model_entries = model_response.get("data")
            if not isinstance(model_entries, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("id"), str)
                for item in model_entries
            ):
                raise LlamaCppError(
                    "INVALID_LOCAL_RESPONSE", "llama.cpp returned an invalid model list."
                )
            available_models = [item["id"] for item in model_entries]
            return {
                "reachable": True,
                "health": health.get("status", "available"),
                "model_alias": properties.get("default_generation_settings", {}).get(
                    "model"
                ),
                "chat_template_reported": bool(
                    properties.get("default_generation_settings", {}).get(
                        "chat_template"
                    )
                    or properties.get("chat_template")
                ),
                "requested_model": self.config.model,
                "available_models": available_models,
                "model_id_verified": self.config.model in available_models,
                "tool_calling_verified": False,
                "json_schema_verified": False,
            }
        except LlamaCppError as exc:
            return {
                "reachable": False,
                "error_code": exc.code,
                "requested_model": self.config.model,
                "available_models": [],
                "model_id_verified": False,
                "tool_calling_verified": False,
                "json_schema_verified": False,
            }

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]],
        response_schema: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "reschedule_proposal",
                    "strict": True,
                    "schema": response_schema,
                },
            },
            "chat_template_kwargs": {
                "enable_thinking": self.config.thinking_mode == ThinkingMode.THINK
            },
        }
        return self._request(
            "/v1/chat/completions",
            payload=payload,
            timeout_seconds=timeout_seconds,
        )


class QwenProposalAgent:
    SYSTEM_PROMPT = (
        "You interpret a user's meeting reschedule request. Return only the "
        "requested RescheduleProposalDraft JSON. You may call only the provided "
        "read-only tools to inspect current meeting context. Never optimize, "
        "create candidates, change availability for another person, approve, "
        "finalize, or claim a change was applied. Do not infer a participant ID "
        "from a name; use the authoritative participant IDs shown in context. "
        "If date, time, target, or requested change is ambiguous, populate "
        "ambiguities and do not invent missing values. Times are integer minutes "
        "after midnight in Asia/Seoul."
    )

    def __init__(
        self,
        client: LlamaCppClient,
        tools: ReadOnlyMeetingTools,
        *,
        total_timeout_seconds: float | None = None,
        max_tool_calls: int | None = None,
    ) -> None:
        self.client = client
        self.dispatcher = ReadOnlyToolDispatcher(tools)
        self.total_timeout_seconds = (
            total_timeout_seconds or client.config.total_timeout_seconds
        )
        self.max_tool_calls = (
            client.config.max_tool_calls if max_tool_calls is None else max_tool_calls
        )
        self._tool_calls_for_request = 0

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return RescheduleProposalDraft.model_json_schema()

    @staticmethod
    def _extract_message(response: dict[str, Any]) -> dict[str, Any]:
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlamaCppError(
                "INVALID_LOCAL_RESPONSE", "llama.cpp response omitted a chat message."
            ) from exc
        if not isinstance(message, dict):
            raise LlamaCppError(
                "INVALID_LOCAL_RESPONSE", "llama.cpp chat message is malformed."
            )
        return message

    def _chat(
        self, messages: list[dict[str, Any]], deadline: float
    ) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LlamaCppError(
                "LOCAL_INFERENCE_TIMEOUT", "The total local inference deadline expired."
            )
        return self.client.chat(
            messages,
            tools=ReadOnlyToolDispatcher.definitions(),
            response_schema=self._response_schema(),
            timeout_seconds=min(self.client.config.request_timeout_seconds, remaining),
        )

    def propose(
        self,
        request_text: str,
        snapshot: MeetingSnapshot,
        actor: ProposalActor,
        *,
        today: date | None = None,
    ) -> RescheduleProposal:
        if not request_text.strip():
            raise ProposalValidationError("EMPTY_REQUEST", "Enter a reschedule request.")
        self._tool_calls_for_request = 0
        self.dispatcher.call_count = 0
        deadline = time.monotonic() + self.total_timeout_seconds
        participant_context = [
            {
                "participantId": participant.participant_id,
                "displayName": participant.display_name,
                "role": participant.role.value,
                "responseStatus": participant.response_status.value,
            }
            for participant in snapshot.participants
            if participant.response_status == ResponseStatus.ACCEPTED
        ]
        user_context = {
            "request": request_text,
            "baseInputRevision": snapshot.input_revision,
            "today": (today or date.today()).isoformat(),
            "timeZone": snapshot.time_zone,
            "participants": participant_context,
        }
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(user_context, ensure_ascii=False),
            },
        ]

        for _ in range(self.max_tool_calls + 1):
            response = self._chat(messages, deadline)
            message = self._extract_message(response)
            tool_calls = message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                raise LlamaCppError("INVALID_LOCAL_RESPONSE", "Tool call list is malformed.")
            if not tool_calls:
                content = message.get("content")
                if not isinstance(content, str) or not content:
                    raise LlamaCppError(
                        "INVALID_MODEL_OUTPUT", "The model returned no proposal JSON."
                    )
                draft = parse_proposal_payload(
                    content, base_revision=snapshot.input_revision
                )
                proposal = validate_proposal(
                    snapshot, actor, draft, today=today
                )
                if proposal.status.value == "CLARIFICATION_REQUIRED":
                    return proposal
                return proposal

            if self._tool_calls_for_request + len(tool_calls) > self.max_tool_calls:
                raise LlamaCppError(
                    "TOOL_CALL_LIMIT", "The model exceeded the read-only tool call limit."
                )
            messages.append(message)
            for call in tool_calls:
                try:
                    call_id = call["id"]
                    function = call["function"]
                    name = function["name"]
                    arguments = function["arguments"]
                except (KeyError, TypeError) as exc:
                    raise LlamaCppError(
                        "INVALID_TOOL_CALL", "The model returned a malformed tool call."
                    ) from exc
                if not all(isinstance(value, str) for value in (call_id, name, arguments)):
                    raise LlamaCppError(
                        "INVALID_TOOL_CALL", "The model returned a malformed tool call."
                    )
                result = self.dispatcher.invoke(
                    name,
                    arguments,
                    max_calls=self.max_tool_calls,
                    timeout_seconds=min(
                        self.client.config.tool_timeout_seconds,
                        max(0.0, deadline - time.monotonic()),
                    ),
                )
                self._tool_calls_for_request += 1
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        raise LlamaCppError(
            "TOOL_CALL_LIMIT", "The model did not return a proposal within the tool-call limit."
        )


def build_proposal_agent(
    snapshot: MeetingSnapshot,
    *,
    config: LlamaCppConfig | None = None,
) -> QwenProposalAgent:
    return QwenProposalAgent(
        LlamaCppClient(config),
        LocalSnapshotReadTools(snapshot),
    )
