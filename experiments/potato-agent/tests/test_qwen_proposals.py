from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any

import pytest

from potato_agent.candidate_validator import validate_solver_candidates
from potato_agent.fixtures import SAMPLE_DATE, sample_snapshot
from potato_agent.llama_cpp import (
    LlamaCppClient,
    LlamaCppConfig,
    LlamaCppError,
    LocalSnapshotReadTools,
    QwenProposalAgent,
    ReadOnlyToolDispatcher,
    ThinkingMode,
)
from potato_agent.models import (
    AbsoluteTimeWindow,
    AvailabilitySlot,
    RecommendationType,
    SolverStatus,
)
from potato_agent.ortools_adapter import CpSatSolverAdapter
from potato_agent.qwen_proposals import (
    LocalProposalApprovalAdapter,
    ProposalActor,
    ProposalScope,
    ProposalStatus,
    ProposalValidationError,
    RescheduleProposalDraft,
    parse_proposal_payload,
    proposal_scope,
    validate_proposal,
)

TODAY = date(2026, 11, 1)


def _actor(participant_id: str = "organizer-1", *, can_edit_own=False):
    return ProposalActor(
        participant_id=participant_id,
        can_edit_own_availability=can_edit_own,
    )


def _draft(changes, *, ambiguities=(), revision=7, summary="Fixture proposal"):
    return RescheduleProposalDraft(
        base_input_revision=revision,
        changes=tuple(changes),
        ambiguities=tuple(ambiguities),
        summary=summary,
    )


def _multi_date_snapshot():
    snapshot = sample_snapshot()
    second_date = SAMPLE_DATE + timedelta(days=1)
    payload = snapshot.model_dump(mode="python")
    payload["dates"] = (SAMPLE_DATE, second_date)
    payload["availability_by_participant_id"] = {
        participant_id: submission.model_copy(
            update={
                "slots": (
                    *submission.slots,
                    AvailabilitySlot(
                        date=second_date,
                        start_minute=600,
                        end_minute=720,
                    ),
                )
            }
        )
        for participant_id, submission
        in snapshot.availability_by_participant_id.items()
    }
    return type(snapshot).model_validate(payload), second_date


def _llm_response(content: str):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }


def _tool_call(name: str, arguments: str):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-local-1",
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ],
                }
            }
        ]
    }


class ScriptedClient:
    def __init__(self, responses, *, config=None):
        self.responses = list(responses)
        self.config = config or LlamaCppConfig()
        self.requests = []

    def chat(self, messages, *, tools, response_schema, timeout_seconds):
        self.requests.append(
            {
                "messages": messages,
                "tools": tools,
                "response_schema": response_schema,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.responses.pop(0)


def _fixture_agent(output: dict[str, Any], *, client=None, snapshot=None):
    serialized = json.dumps(output, ensure_ascii=False)
    scripted = client or ScriptedClient([_llm_response(serialized)])
    meeting = snapshot or sample_snapshot()
    return QwenProposalAgent(scripted, LocalSnapshotReadTools(meeting)), scripted, meeting


def test_fixture_korean_date_change_produces_proposed_snapshot_change():
    snapshot = sample_snapshot()
    output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [{"kind": "SET_MEETING_DATES", "dates": [SAMPLE_DATE.isoformat()]}],
        "ambiguities": [],
        "summary": "11월 8일 일정으로 변경합니다.",
    }
    agent, _, _ = _fixture_agent(output, snapshot=snapshot)

    proposal = agent.propose(
        "11월 8일로 바꿔줘", snapshot, _actor(), today=TODAY
    )

    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.changes[0].kind == "SET_MEETING_DATES"


def test_fixture_afternoon_time_is_preserved_as_exact_minute():
    snapshot = sample_snapshot()
    output = {
        "base_input_revision": 7,
        "changes": [
            {
                "kind": "SET_START_TIME",
                "date": SAMPLE_DATE.isoformat(),
                "minute": 15 * 60,
            }
        ],
        "ambiguities": [],
        "summary": "오후 3시에 시작합니다.",
    }
    agent, _, _ = _fixture_agent(output, snapshot=snapshot)

    proposal = agent.propose("오후 3시에 시작해줘", snapshot, _actor(), today=TODAY)
    updated = LocalProposalApprovalAdapter().approve(
        snapshot, _actor(), proposal, today=TODAY
    )

    assert updated.required_start_minutes_by_date[SAMPLE_DATE] == 900
    assert updated.input_revision == 8


def test_fixture_minute_precision_is_not_rounded():
    snapshot = sample_snapshot()
    output = {
        "base_input_revision": 7,
        "changes": [
            {
                "kind": "SET_START_TIME",
                "date": SAMPLE_DATE.isoformat(),
                "minute": 17 * 60 + 3,
            },
            {"kind": "SET_DURATION", "duration_minutes": 45},
        ],
        "ambiguities": [],
        "summary": "17시 3분에 45분간 진행합니다.",
    }
    agent, _, _ = _fixture_agent(output, snapshot=snapshot)

    proposal = agent.propose("17시 3분부터 45분", snapshot, _actor(), today=TODAY)
    updated = LocalProposalApprovalAdapter().approve(
        snapshot, _actor(), proposal, today=TODAY
    )

    assert updated.required_start_minutes_by_date[SAMPLE_DATE] == 1023
    assert updated.duration_minutes == 45


def test_fixture_duration_change_is_applied_only_after_confirmation():
    snapshot = sample_snapshot()
    proposal = validate_proposal(
        snapshot,
        _actor(),
        _draft([{"kind": "SET_DURATION", "duration_minutes": 45}]),
        today=TODAY,
    )

    updated = LocalProposalApprovalAdapter().approve(
        snapshot, _actor(), proposal, today=TODAY
    )

    assert updated.duration_minutes == 45
    assert updated.input_revision == snapshot.input_revision + 1


@pytest.mark.parametrize(
    ("request_text", "duration_minutes"),
    [
        ("소요시간을 45분으로 줄여줘", 45),
        ("모임 시간을 30분 늘려줘", 90),
    ],
)
def test_fixture_duration_language_maps_to_set_duration(
    request_text, duration_minutes
):
    snapshot = sample_snapshot()
    output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [
            {"kind": "SET_DURATION", "duration_minutes": duration_minutes}
        ],
        "ambiguities": [],
        "summary": f"소요시간을 {duration_minutes}분으로 변경합니다.",
    }
    agent, client, _ = _fixture_agent(output, snapshot=snapshot)
    snapshot_before = snapshot.model_dump(mode="json")

    proposal = agent.propose(
        request_text, snapshot, _actor(), today=TODAY
    )

    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.changes[0].kind == "SET_DURATION"
    assert proposal.changes[0].duration_minutes == duration_minutes
    assert snapshot.model_dump(mode="json") == snapshot_before
    assert "소요시간을 45분으로 줄여줘" in client.requests[0]["messages"][0]["content"]
    assert "REMOVE_TIME_WINDOW" in client.requests[0]["messages"][0]["content"]


def test_explicit_removal_requires_an_existing_exact_time_window():
    snapshot = sample_snapshot().model_copy(
        update={
            "absolute_time_windows": (
                AbsoluteTimeWindow(
                    date=SAMPLE_DATE,
                    start_minute=20 * 60,
                    end_minute=21 * 60,
                ),
            )
        }
    )
    existing_change = {
        "kind": "REMOVE_TIME_WINDOW",
        "date": SAMPLE_DATE.isoformat(),
        "start_minute": 20 * 60,
        "end_minute": 21 * 60,
    }
    proposal = validate_proposal(
        snapshot, _actor(), _draft([existing_change]), today=TODAY
    )
    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.changes[0].kind == "REMOVE_TIME_WINDOW"

    missing_change = {
        **existing_change,
        "start_minute": 19 * 60,
        "end_minute": 20 * 60,
    }
    with pytest.raises(ProposalValidationError) as error:
        validate_proposal(
            snapshot, _actor(), _draft([missing_change]), today=TODAY
        )
    assert error.value.code == "CONDITION_NOT_FOUND"


def test_fixture_explicit_clock_window_removal_uses_existing_condition():
    snapshot = sample_snapshot().model_copy(
        update={
            "absolute_time_windows": (
                AbsoluteTimeWindow(
                    date=SAMPLE_DATE,
                    start_minute=20 * 60,
                    end_minute=21 * 60,
                ),
            )
        }
    )
    output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [
            {
                "kind": "REMOVE_TIME_WINDOW",
                "date": SAMPLE_DATE.isoformat(),
                "start_minute": 20 * 60,
                "end_minute": 21 * 60,
            }
        ],
        "ambiguities": [],
        "summary": "11월 8일 오후 8시부터 9시까지 조건을 삭제합니다.",
    }
    agent, _, _ = _fixture_agent(output, snapshot=snapshot)

    proposal = agent.propose(
        "11월 8일 오후 8시부터 9시까지 조건을 삭제해줘",
        snapshot,
        _actor(),
        today=TODAY,
    )

    assert proposal.status == ProposalStatus.PROPOSED
    change = proposal.changes[0]
    assert change.kind == "REMOVE_TIME_WINDOW"
    assert change.date == SAMPLE_DATE
    assert change.start_minute == 20 * 60
    assert change.end_minute == 21 * 60


def test_domain_validation_failure_regenerates_once_with_error_feedback():
    snapshot = sample_snapshot()
    invalid_output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [
            {
                "kind": "REMOVE_TIME_WINDOW",
                "date": SAMPLE_DATE.isoformat(),
                "start_minute": 20 * 60,
                "end_minute": 21 * 60,
            }
        ],
        "ambiguities": [],
        "summary": "오후 8시부터 9시까지 조건을 삭제합니다.",
    }
    corrected_output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [{"kind": "SET_DURATION", "duration_minutes": 45}],
        "ambiguities": [],
        "summary": "소요시간을 45분으로 변경합니다.",
    }
    client = ScriptedClient(
        [
            _llm_response(json.dumps(invalid_output, ensure_ascii=False)),
            _llm_response(json.dumps(corrected_output, ensure_ascii=False)),
        ]
    )
    agent, _, _ = _fixture_agent(corrected_output, client=client, snapshot=snapshot)
    snapshot_before = snapshot.model_dump(mode="json")
    revision_before = snapshot.input_revision
    consent_round_before = snapshot.consent_round

    proposal = agent.propose(
        "소요시간을 45분으로 줄여줘",
        snapshot,
        _actor(),
        today=TODAY,
    )

    retry_feedback = json.loads(client.requests[1]["messages"][-1]["content"])
    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.changes[0].kind == "SET_DURATION"
    assert proposal.changes[0].duration_minutes == 45
    assert retry_feedback["validationError"]["code"] == "CONDITION_NOT_FOUND"
    assert set(retry_feedback["allowedChangeTypes"]) == set(
        agent.ALLOWED_CHANGE_TYPES
    )
    assert "do not" in retry_feedback["instruction"]
    assert snapshot.model_dump(mode="json") == snapshot_before
    assert snapshot.input_revision == revision_before
    assert snapshot.consent_round == consent_round_before


def test_schema_validation_failure_regenerates_once():
    snapshot = sample_snapshot()
    corrected_output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [{"kind": "SET_DURATION", "duration_minutes": 45}],
        "ambiguities": [],
        "summary": "소요시간을 45분으로 변경합니다.",
    }
    client = ScriptedClient(
        [
            _llm_response("not valid JSON"),
            _llm_response(json.dumps(corrected_output, ensure_ascii=False)),
        ]
    )
    agent, _, _ = _fixture_agent(corrected_output, client=client, snapshot=snapshot)

    proposal = agent.propose(
        "소요시간을 45분으로 줄여줘", snapshot, _actor(), today=TODAY
    )

    retry_feedback = json.loads(client.requests[1]["messages"][-1]["content"])
    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.changes[0].kind == "SET_DURATION"
    assert retry_feedback["validationError"]["code"] == "INVALID_MODEL_OUTPUT"


def test_second_validation_failure_exits_without_applying_proposal():
    snapshot = sample_snapshot()
    invalid_output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [
            {
                "kind": "REMOVE_TIME_WINDOW",
                "date": SAMPLE_DATE.isoformat(),
                "start_minute": 20 * 60,
                "end_minute": 21 * 60,
            }
        ],
        "ambiguities": [],
        "summary": "존재하는지 확인되지 않은 시간창을 삭제합니다.",
    }
    invalid_response = _llm_response(
        json.dumps(invalid_output, ensure_ascii=False)
    )
    client = ScriptedClient([invalid_response, invalid_response])
    agent, _, _ = _fixture_agent(invalid_output, client=client, snapshot=snapshot)
    snapshot_before = snapshot.model_dump(mode="json")

    with pytest.raises(ProposalValidationError) as error:
        agent.propose(
            "오후 8시부터 9시까지 조건을 삭제해줘",
            snapshot,
            _actor(),
            today=TODAY,
        )

    assert error.value.code == "PROPOSAL_RETRY_EXHAUSTED"
    assert isinstance(error.value.__cause__, ProposalValidationError)
    assert error.value.__cause__.code == "CONDITION_NOT_FOUND"
    assert len(client.requests) == 2
    assert snapshot.model_dump(mode="json") == snapshot_before


def test_fixture_excludes_one_date_without_deleting_submitted_slots():
    snapshot, second_date = _multi_date_snapshot()
    draft = _draft(
        [{"kind": "SET_MEETING_DATES", "dates": [second_date.isoformat()]}]
    )
    proposal = validate_proposal(snapshot, _actor(), draft, today=TODAY)

    updated = LocalProposalApprovalAdapter().approve(
        snapshot, _actor(), proposal, today=TODAY
    )

    assert updated.dates == snapshot.dates
    assert updated.excluded_dates == (SAMPLE_DATE,)
    assert updated.availability_by_participant_id["organizer-1"].slots == (
        snapshot.availability_by_participant_id["organizer-1"].slots
    )
    result = CpSatSolverAdapter(updated).solve_all_attendees(updated)
    assert result.status == SolverStatus.OPTIMAL
    assert all(candidate.date == second_date for candidate in result.candidates)


def test_fixture_combines_date_duration_and_absolute_condition_changes():
    snapshot, second_date = _multi_date_snapshot()
    output = {
        "base_input_revision": 7,
        "changes": [
            {"kind": "SET_MEETING_DATES", "dates": [second_date.isoformat()]},
            {"kind": "SET_DURATION", "duration_minutes": 30},
            {
                "kind": "ADD_TIME_WINDOW",
                "date": second_date.isoformat(),
                "start_minute": 610,
                "end_minute": 650,
            },
        ],
        "ambiguities": [],
        "summary": "둘째 날짜에 30분 일정 시간 조건을 추가합니다.",
    }
    agent, _, _ = _fixture_agent(output, snapshot=snapshot)
    proposal = agent.propose("다음 날짜 10시 10분에서 10시 50분 사이 30분", snapshot, _actor(), today=TODAY)

    updated = LocalProposalApprovalAdapter().approve(
        snapshot, _actor(), proposal, today=TODAY
    )
    result = CpSatSolverAdapter(updated).solve_all_attendees(updated)
    validated = validate_solver_candidates(
        updated,
        result,
        RecommendationType.ALL_AVAILABLE,
        result.status,
        updated.input_revision,
    )

    assert updated.excluded_dates == (SAMPLE_DATE,)
    assert updated.duration_minutes == 30
    assert updated.absolute_time_windows == (
        AbsoluteTimeWindow(
            date=second_date, start_minute=610, end_minute=650
        ),
    )
    assert result.status == SolverStatus.OPTIMAL
    assert validated[0].date == second_date
    assert validated[0].start_minute == 610


def test_ambiguous_request_requires_clarification_and_cannot_be_approved():
    snapshot = sample_snapshot()
    output = {
        "base_input_revision": 7,
        "changes": [],
        "ambiguities": ["요청한 날짜를 확인해 주세요."],
        "summary": "날짜를 확인해야 합니다.",
    }
    agent, _, _ = _fixture_agent(output, snapshot=snapshot)
    proposal = agent.propose("다음 주로 바꿔줘", snapshot, _actor(), today=TODAY)

    assert proposal.status == ProposalStatus.CLARIFICATION_REQUIRED
    with pytest.raises(ProposalValidationError, match="unambiguous"):
        LocalProposalApprovalAdapter().approve(
            snapshot, _actor(), proposal, today=TODAY
        )


def test_invalid_model_json_is_rejected_without_fallback_parsing():
    with pytest.raises(ProposalValidationError) as error:
        parse_proposal_payload("{not-json", base_revision=7)
    assert error.value.code == "INVALID_MODEL_OUTPUT"


@pytest.mark.parametrize(
    "payload",
    [
        '{"base_input_revision":7,"changes":[{"kind":"UNKNOWN"}],"ambiguities":[],"summary":"x"}',
        '{"base_input_revision":7,"changes":[{"kind":"SET_DURATION","duration_minutes":0}],"ambiguities":[],"summary":"x"}',
        '{"base_input_revision":7,"changes":[{"kind":"SET_START_TIME","date":"2026-99-99","minute":600}],"ambiguities":[],"summary":"x"}',
    ],
)
def test_invalid_change_or_date_is_rejected(payload):
    with pytest.raises(ProposalValidationError) as error:
        parse_proposal_payload(payload, base_revision=7)
    assert error.value.code == "INVALID_MODEL_OUTPUT"


def test_request_with_nonexistent_participant_is_rejected():
    snapshot = sample_snapshot()
    draft = _draft(
        [
            {
                "kind": "SET_PERSONAL_AVAILABILITY",
                "participant_id": "not-a-meeting-participant",
                "date": SAMPLE_DATE.isoformat(),
                "slots": [
                    {
                        "date": SAMPLE_DATE.isoformat(),
                        "start_minute": 600,
                        "end_minute": 660,
                    }
                ],
            }
        ]
    )
    with pytest.raises(ProposalValidationError) as error:
        validate_proposal(snapshot, _actor(), draft, today=TODAY)
    assert error.value.code == "PARTICIPANT_NOT_FOUND"


def test_invitee_cannot_change_meeting_constraints():
    snapshot = sample_snapshot()
    with pytest.raises(ProposalValidationError) as error:
        validate_proposal(
            snapshot,
            _actor("invitee-1"),
            _draft([{"kind": "SET_DURATION", "duration_minutes": 45}]),
            today=TODAY,
        )
    assert error.value.code == "HOST_REQUIRED"


def test_participant_can_change_only_their_own_availability_with_permission():
    snapshot = sample_snapshot()
    change = {
        "kind": "SET_PERSONAL_AVAILABILITY",
        "participant_id": "invitee-1",
        "date": SAMPLE_DATE.isoformat(),
        "slots": [
            {
                "date": SAMPLE_DATE.isoformat(),
                "start_minute": 600,
                "end_minute": 660,
            }
        ],
    }
    proposal = validate_proposal(
        snapshot,
        _actor("invitee-1", can_edit_own=True),
        _draft([change]),
        today=TODAY,
    )
    assert proposal_scope(proposal.changes[0]) == ProposalScope.PERSONAL_AVAILABILITY

    with pytest.raises(ProposalValidationError) as error:
        validate_proposal(
            snapshot,
            _actor("organizer-1", can_edit_own=True),
            _draft([change]),
            today=TODAY,
        )
    assert error.value.code == "AVAILABILITY_PERMISSION_DENIED"


def test_revision_does_not_change_until_local_approval():
    snapshot = sample_snapshot()
    proposal = validate_proposal(
        snapshot,
        _actor(),
        _draft([{"kind": "SET_DURATION", "duration_minutes": 30}]),
        today=TODAY,
    )

    assert snapshot.input_revision == 7
    rejected = LocalProposalApprovalAdapter().reject(snapshot, proposal)
    assert rejected.input_revision == 7
    assert rejected.duration_minutes == snapshot.duration_minutes
    approved = LocalProposalApprovalAdapter().approve(
        snapshot, _actor(), proposal, today=TODAY
    )
    assert approved.input_revision == 8


def test_stale_proposal_is_rejected_at_approval():
    snapshot = sample_snapshot()
    proposal = validate_proposal(
        snapshot,
        _actor(),
        _draft([{"kind": "SET_DURATION", "duration_minutes": 30}]),
        today=TODAY,
    )
    changed_snapshot = snapshot.model_copy(update={"input_revision": 8})

    with pytest.raises(ProposalValidationError) as error:
        LocalProposalApprovalAdapter().approve(
            changed_snapshot, _actor(), proposal, today=TODAY
        )
    assert error.value.code == "STALE_INPUT_REVISION"


def test_confirmed_proposal_runs_cp_sat_again_and_validates_result():
    snapshot = sample_snapshot()
    proposal = validate_proposal(
        snapshot,
        _actor(),
        _draft([{"kind": "SET_DURATION", "duration_minutes": 30}]),
        today=TODAY,
    )
    updated = LocalProposalApprovalAdapter().approve(
        snapshot, _actor(), proposal, today=TODAY
    )
    result = CpSatSolverAdapter(updated).solve_all_attendees(updated)
    validated = validate_solver_candidates(
        updated,
        result,
        RecommendationType.ALL_AVAILABLE,
        result.status,
        updated.input_revision,
    )

    assert result.status == SolverStatus.OPTIMAL
    assert result.candidates[0].end_minute - result.candidates[0].start_minute == 30
    assert validated[0].verified is True
    assert validated[0].source_revision == 8


def test_read_only_tool_allowlist_never_exposes_mutating_tools():
    names = {
        item["function"]["name"]
        for item in ReadOnlyToolDispatcher.definitions()
    }
    assert names == {
        "get_availability",
        "get_meeting_constraints",
        "find_common_slots",
    }
    dispatcher = ReadOnlyToolDispatcher(LocalSnapshotReadTools(sample_snapshot()))
    for forbidden in ("optimize_schedule", "save_candidates", "approval", "finalize"):
        with pytest.raises(LlamaCppError) as error:
            dispatcher.invoke(
                forbidden,
                "{}",
                max_calls=3,
                timeout_seconds=1,
            )
        assert error.value.code == "TOOL_NOT_ALLOWED"


def test_tool_argument_schema_is_checked_and_tool_calls_are_capped():
    dispatcher = ReadOnlyToolDispatcher(LocalSnapshotReadTools(sample_snapshot()))
    with pytest.raises(LlamaCppError) as error:
        dispatcher.invoke(
            "get_availability",
            '{"participant_id":"organizer-1","extra":true}',
            max_calls=3,
            timeout_seconds=1,
        )
    assert error.value.code == "INVALID_TOOL_ARGUMENTS"

    dispatcher.invoke(
        "get_meeting_constraints", "{}", max_calls=1, timeout_seconds=1
    )
    with pytest.raises(LlamaCppError) as error:
        dispatcher.invoke(
            "get_meeting_constraints",
            "{}",
            max_calls=1,
            timeout_seconds=1,
        )
    assert error.value.code == "TOOL_CALL_LIMIT"


def test_read_only_tool_timeout_is_explicit():
    class SlowTools(LocalSnapshotReadTools):
        def get_meeting_constraints(self):
            time.sleep(0.05)
            return super().get_meeting_constraints()

    dispatcher = ReadOnlyToolDispatcher(SlowTools(sample_snapshot()))
    with pytest.raises(LlamaCppError) as error:
        dispatcher.invoke(
            "get_meeting_constraints",
            "{}",
            max_calls=3,
            timeout_seconds=0.001,
        )
    assert error.value.code == "TOOL_TIMEOUT"


def test_qwen_uses_only_read_tools_and_json_schema_response():
    snapshot = sample_snapshot()
    output = {
        "base_input_revision": 7,
        "changes": [{"kind": "SET_DURATION", "duration_minutes": 45}],
        "ambiguities": [],
        "summary": "45분으로 변경합니다.",
    }
    client = ScriptedClient(
        [
            _tool_call("get_meeting_constraints", "{}"),
            _llm_response(json.dumps(output)),
        ]
    )
    agent, _, _ = _fixture_agent(output, client=client, snapshot=snapshot)

    proposal = agent.propose("45분으로 줄여줘", snapshot, _actor(), today=TODAY)

    assert proposal.status == ProposalStatus.PROPOSED
    assert len(client.requests) == 2
    assert {
        tool["function"]["name"]
        for tool in client.requests[0]["tools"]
    } == {
        "get_availability",
        "get_meeting_constraints",
        "find_common_slots",
    }
    assert client.requests[0]["response_schema"]["additionalProperties"] is False
    assert client.requests[1]["messages"][-1]["role"] == "tool"


def test_qwen_returns_multiple_tool_results_with_matching_call_ids():
    snapshot = sample_snapshot()
    output = {
        "base_input_revision": snapshot.input_revision,
        "changes": [{"kind": "SET_DURATION", "duration_minutes": 45}],
        "ambiguities": [],
        "summary": "45분으로 변경합니다.",
    }
    client = ScriptedClient(
        [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-constraints",
                                    "type": "function",
                                    "function": {
                                        "name": "get_meeting_constraints",
                                        "arguments": "{}",
                                    },
                                },
                                {
                                    "id": "call-slots",
                                    "type": "function",
                                    "function": {
                                        "name": "find_common_slots",
                                        "arguments": json.dumps(
                                            {"date": SAMPLE_DATE.isoformat()}
                                        ),
                                    },
                                },
                            ],
                        }
                    }
                ]
            },
            _llm_response(json.dumps(output)),
        ]
    )
    agent, _, _ = _fixture_agent(output, client=client, snapshot=snapshot)

    proposal = agent.propose(
        "제약과 공통 가능 시간을 확인하고 45분으로 바꿔줘",
        snapshot,
        _actor(),
        today=TODAY,
    )

    tool_messages = [
        item
        for item in client.requests[1]["messages"]
        if item["role"] == "tool"
    ]
    assert proposal.status == ProposalStatus.PROPOSED
    assert [item["tool_call_id"] for item in tool_messages] == [
        "call-constraints",
        "call-slots",
    ]
    assert agent.dispatcher.call_count == 2


def test_disallowed_tool_call_fails_without_fallback():
    snapshot = sample_snapshot()
    client = ScriptedClient([_tool_call("finalize", "{}")])
    agent, _, _ = _fixture_agent({}, client=client, snapshot=snapshot)

    with pytest.raises(LlamaCppError) as error:
        agent.propose("다음 주로 옮겨줘", snapshot, _actor(), today=TODAY)
    assert error.value.code == "TOOL_NOT_ALLOWED"


def test_tool_call_argument_json_is_validated_before_read():
    snapshot = sample_snapshot()
    client = ScriptedClient([_tool_call("get_availability", "{invalid")])
    agent, _, _ = _fixture_agent({}, client=client, snapshot=snapshot)

    with pytest.raises(LlamaCppError) as error:
        agent.propose("가능 시간 알려줘", snapshot, _actor(), today=TODAY)
    assert error.value.code == "INVALID_TOOL_ARGUMENTS"


def test_think_modes_are_independent_configuration_options():
    think = LlamaCppClient(
        LlamaCppConfig(thinking_mode=ThinkingMode.THINK)
    )
    no_think = LlamaCppClient(
        LlamaCppConfig(thinking_mode=ThinkingMode.NO_THINK)
    )

    assert think.config.thinking_mode != no_think.config.thinking_mode


def test_llama_cpp_endpoint_must_be_loopback_only():
    with pytest.raises(ValueError):
        LlamaCppClient(LlamaCppConfig(base_url="https://example.com"))
    with pytest.raises(ValueError, match="port 8080"):
        LlamaCppClient(LlamaCppConfig(base_url="http://127.0.0.1:8080"))
    client = LlamaCppClient(
        LlamaCppConfig(
            base_url="http://127.0.0.1:18081",
            model="potato-qwen-test",
        )
    )
    assert client.config.base_url == "http://127.0.0.1:18081"
    assert client.config.model == "potato-qwen-test"


def test_health_probe_checks_the_configured_model_id(monkeypatch):
    client = LlamaCppClient(
        LlamaCppConfig(
            base_url="http://127.0.0.1:18081",
            model="potato-qwen-test",
        )
    )
    responses = {
        "/health": {"status": "ok"},
        "/props": {
            "default_generation_settings": {
                "model": "potato-qwen-test",
                "chat_template": "reported",
            }
        },
        "/v1/models": {"data": [{"id": "potato-qwen-test"}]},
    }

    def request(path):
        return responses[path]

    monkeypatch.setattr(client, "_request", request)

    result = client.probe()

    assert result["reachable"] is True
    assert result["model_id_verified"] is True
    assert result["available_models"] == ["potato-qwen-test"]
    assert result["tool_calling_verified"] is False
    assert result["json_schema_verified"] is False
