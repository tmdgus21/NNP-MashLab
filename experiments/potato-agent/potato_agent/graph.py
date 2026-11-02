from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from potato_agent.models import (
    AgentStatus,
    AvailabilityStatus,
    AvailabilitySlot,
    AvailabilitySubmission,
    Candidate,
    CandidateSelection,
    ConsentDecision,
    ConsentSubmission,
    EligibilityStatus,
    HostApprovalSubmission,
    InvitationStatus,
    MeetingSnapshot,
    Participant,
    ParticipantRole,
    ReadinessReport,
    RawCandidate,
    RecommendationType,
    ResponseStatus,
    SolverResult,
    SolverStatus,
)
from potato_agent.candidate_validator import (
    CandidateValidationError,
    StaleInputRevision,
    validate_solver_candidates,
)
from potato_agent.tools import SolverAdapter

_CHECKPOINT_TYPES = [
    AgentStatus,
    AvailabilitySlot,
    AvailabilityStatus,
    AvailabilitySubmission,
    Candidate,
    EligibilityStatus,
    InvitationStatus,
    MeetingSnapshot,
    Participant,
    ParticipantRole,
    ReadinessReport,
    RawCandidate,
    RecommendationType,
    ResponseStatus,
    SolverResult,
    SolverStatus,
    ConsentDecision,
]


class AgentState(TypedDict, total=False):
    meeting_id: str
    snapshot: MeetingSnapshot
    status: AgentStatus
    readiness: ReadinessReport
    all_result: SolverResult
    partial_result: SolverResult
    all_solver_status: SolverStatus
    partial_solver_status: SolverStatus
    candidates: list[Candidate]
    selected_candidate_id: str
    consent_by_attendee_id: dict[str, str]
    consent_declined: bool
    selection_response: Any
    consent_response: Any
    approval_response: Any
    approval_decision: Literal["APPROVED", "REJECTED"]
    meeting_finalized: bool
    error: dict[str, Any]


def _active_accepted_participants(snapshot: MeetingSnapshot) -> list[Participant]:
    return [
        participant
        for participant in snapshot.participants
        if participant.response_status == ResponseStatus.ACCEPTED
        and participant.eligibility_status.value == "ACTIVE"
    ]


def _classify_readiness(snapshot: MeetingSnapshot) -> ReadinessReport:
    pending_rsvp = tuple(
        participant.participant_id
        for participant in snapshot.participants
        if participant.response_status == ResponseStatus.PENDING
        and participant.eligibility_status.value == "ACTIVE"
    )
    missing_availability = []
    for participant in _active_accepted_participants(snapshot):
        submission = snapshot.availability_by_participant_id.get(participant.participant_id)
        if submission is None or submission.status == AvailabilityStatus.NOT_SUBMITTED:
            missing_availability.append(participant.participant_id)
    return ReadinessReport(
        pending_rsvp_ids=pending_rsvp,
        availability_not_submitted_ids=tuple(missing_availability),
    )


def _error(code: str, message: str, retryable: bool = False) -> dict[str, Any]:
    return {"code": code, "message": message, "retryable": retryable}


def _check_current_revision(snapshot: MeetingSnapshot, tools: SolverAdapter) -> None:
    if tools.current_input_revision(snapshot.meeting_id) != snapshot.input_revision:
        raise StaleInputRevision("The meeting input revision changed.")


def _validate_result_node(
    state: AgentState,
    tools: SolverAdapter,
    recommendation_type: RecommendationType,
    result: SolverResult,
    all_status: SolverStatus,
) -> dict[str, Any]:
    snapshot = state["snapshot"]
    try:
        candidates = validate_solver_candidates(
            snapshot,
            result,
            recommendation_type,
            all_status,
            tools.current_input_revision(snapshot.meeting_id),
        )
    except StaleInputRevision:
        return {"status": AgentStatus.STALE, "candidates": []}
    except CandidateValidationError:
        return {
            "status": AgentStatus.ERROR,
            "candidates": [],
            "error": _error(
                "CANDIDATE_VALIDATION_FAILED",
                "The solver result did not pass deterministic validation.",
            ),
        }
    return {
        "status": (
            AgentStatus.ALL_AVAILABLE
            if recommendation_type == RecommendationType.ALL_AVAILABLE
            else AgentStatus.PARTIAL_ALTERNATIVE
        ),
        "candidates": candidates,
    }


def build_agent_graph(tools: SolverAdapter, checkpointer=None):
    builder = StateGraph(AgentState)

    def load_snapshot(state: AgentState) -> dict[str, Any]:
        snapshot = tools.load_snapshot(state["meeting_id"])
        return {"snapshot": snapshot, "status": AgentStatus.ANALYZING, "candidates": []}

    def classify_readiness(state: AgentState) -> dict[str, Any]:
        snapshot = state["snapshot"]
        if tools.current_input_revision(snapshot.meeting_id) != snapshot.input_revision:
            return {"status": AgentStatus.STALE, "readiness": _classify_readiness(snapshot)}
        report = _classify_readiness(snapshot)
        return {
            "readiness": report,
            "status": AgentStatus.ANALYZING if report.ready else AgentStatus.WAITING_FOR_INPUT,
        }

    def route_readiness(state: AgentState) -> str:
        if state["status"] == AgentStatus.STALE:
            return "end"
        return "solve_all" if state["readiness"].ready else "end"

    def solve_all(state: AgentState) -> dict[str, Any]:
        result = tools.solve_all_attendees(state["snapshot"])
        return {
            "all_result": result,
            "all_solver_status": result.status,
            "status": AgentStatus.RUNNING_TOOLS,
        }

    def route_all(state: AgentState) -> str:
        snapshot = state["snapshot"]
        try:
            _check_current_revision(snapshot, tools)
        except StaleInputRevision:
            return "stale"
        status = state["all_solver_status"]
        if status == SolverStatus.STALE:
            return "stale"
        if status == SolverStatus.CANCELLED:
            return "cancelled"
        if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            return "validate_all"
        if status == SolverStatus.INFEASIBLE:
            return "solve_partial"
        return "all_solver_error"

    def stale_after_all(_: AgentState) -> dict[str, Any]:
        return {"status": AgentStatus.STALE, "candidates": []}

    def all_solver_error(state: AgentState) -> dict[str, Any]:
        status = state["all_solver_status"]
        if status == SolverStatus.CANCELLED:
            return {
                "status": AgentStatus.CANCELLED,
                "candidates": [],
                "error": _error("SOLVER_CANCELLED", "The search was cancelled."),
            }
        code = {
            SolverStatus.UNKNOWN: "SOLVER_UNKNOWN",
            SolverStatus.TIMEOUT: "SOLVER_TIMEOUT",
            SolverStatus.MODEL_INVALID: "SOLVER_MODEL_INVALID",
            SolverStatus.ERROR: "SOLVER_ERROR",
        }.get(status, "SOLVER_NOT_RUN")
        return {
            "status": AgentStatus.ERROR,
            "candidates": [],
            "error": _error(
                code,
                "The all-attendee search did not establish a valid result.",
                retryable=status in (SolverStatus.UNKNOWN, SolverStatus.TIMEOUT),
            ),
        }

    def validate_all(state: AgentState) -> dict[str, Any]:
        return _validate_result_node(
            state,
            tools,
            RecommendationType.ALL_AVAILABLE,
            state["all_result"],
            state["all_solver_status"],
        )

    def solve_partial(state: AgentState) -> dict[str, Any]:
        snapshot = state["snapshot"]
        result = tools.solve_partial_attendees(snapshot, snapshot.minimum_attendee_count)
        return {
            "partial_result": result,
            "partial_solver_status": result.status,
            "status": AgentStatus.RUNNING_TOOLS,
        }

    def route_partial(state: AgentState) -> str:
        try:
            _check_current_revision(state["snapshot"], tools)
        except StaleInputRevision:
            return "stale"
        if state["partial_solver_status"] == SolverStatus.STALE:
            return "stale"
        if state["partial_solver_status"] == SolverStatus.CANCELLED:
            return "cancelled"
        if state["partial_solver_status"] in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            return "validate_partial"
        if state["partial_solver_status"] == SolverStatus.INFEASIBLE:
            return "no_schedule"
        return "partial_solver_error"

    def validate_partial(state: AgentState) -> dict[str, Any]:
        return _validate_result_node(
            state,
            tools,
            RecommendationType.PARTIAL_ALTERNATIVE,
            state["partial_result"],
            state["all_solver_status"],
        )

    def no_schedule(_: AgentState) -> dict[str, Any]:
        return {"status": AgentStatus.NO_FEASIBLE_SCHEDULE, "candidates": []}

    def partial_solver_error(state: AgentState) -> dict[str, Any]:
        status = state["partial_solver_status"]
        if status == SolverStatus.CANCELLED:
            return {
                "status": AgentStatus.CANCELLED,
                "candidates": [],
                "error": _error("SOLVER_CANCELLED", "The search was cancelled."),
            }
        code = {
            SolverStatus.UNKNOWN: "SOLVER_UNKNOWN",
            SolverStatus.TIMEOUT: "SOLVER_TIMEOUT",
            SolverStatus.MODEL_INVALID: "SOLVER_MODEL_INVALID",
            SolverStatus.ERROR: "SOLVER_ERROR",
        }.get(status, "SOLVER_NOT_RUN")
        return {
            "status": AgentStatus.ERROR,
            "candidates": [],
            "error": _error(
                code,
                "The partial-attendee search did not establish a valid result.",
                retryable=status in (SolverStatus.UNKNOWN, SolverStatus.TIMEOUT),
            ),
        }

    def route_validated(state: AgentState) -> str:
        if state["status"] in (
            AgentStatus.ALL_AVAILABLE,
            AgentStatus.PARTIAL_ALTERNATIVE,
        ):
            return "await_selection"
        return "end"

    def await_candidate_selection(state: AgentState) -> dict[str, Any]:
        response = interrupt(
            {
                "kind": "candidate_selection",
                "inputRevision": state["snapshot"].input_revision,
                "candidates": [candidate.model_dump(mode="json") for candidate in state["candidates"]],
            }
        )
        return {"selection_response": response}

    def validate_selection(state: AgentState) -> dict[str, Any]:
        response = state.get("selection_response")
        if not isinstance(response, dict):
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_SELECTION", "A candidate selection is required."),
            }
        snapshot = state["snapshot"]
        try:
            selection = CandidateSelection.model_validate(response)
        except ValidationError:
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_SELECTION", "The candidate selection is invalid."),
            }
        if selection.input_revision != snapshot.input_revision:
            return {"status": AgentStatus.STALE, "candidates": []}
        candidate = next(
            (
                item for item in state["candidates"]
                if item.candidate_id == selection.candidate_id
            ),
            None,
        )
        if candidate is None or candidate.source_revision != snapshot.input_revision:
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_CANDIDATE", "The selected candidate is not valid for this run."),
            }
        try:
            _check_current_revision(snapshot, tools)
        except StaleInputRevision:
            return {"status": AgentStatus.STALE, "candidates": []}
        return {"selected_candidate_id": candidate.candidate_id}

    def route_selection(state: AgentState) -> str:
        return "collect_consents" if state.get("selected_candidate_id") else "end"

    def collect_consents(state: AgentState) -> dict[str, Any]:
        candidate = next(
            item for item in state["candidates"]
            if item.candidate_id == state["selected_candidate_id"]
        )
        response = interrupt(
            {
                "kind": "participant_consents",
                "candidateId": candidate.candidate_id,
                "inputRevision": candidate.source_revision,
                "consentRound": state["snapshot"].consent_round,
                "attendeeIds": list(candidate.attendee_ids),
                "alreadyConsentedIds": sorted(
                    participant_id
                    for participant_id, decision in state.get("consent_by_attendee_id", {}).items()
                    if decision == "AGREE"
                ),
            }
        )
        return {"consent_response": response}

    def record_consents(state: AgentState) -> dict[str, Any]:
        response = state.get("consent_response")
        if not isinstance(response, dict):
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_CONSENT", "A consent response is required."),
            }
        try:
            submission = ConsentSubmission.model_validate(response)
        except ValidationError:
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_CONSENT", "Consent decisions must be explicit."),
            }
        snapshot = state["snapshot"]
        if submission.input_revision != snapshot.input_revision:
            return {"status": AgentStatus.STALE, "candidates": []}
        if submission.consent_round != snapshot.consent_round:
            return {"status": AgentStatus.STALE, "candidates": []}
        if submission.candidate_id != state["selected_candidate_id"]:
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_CONSENT", "Consent must match the selected candidate."),
            }
        allowed_ids = set(
            next(
                item.attendee_ids
                for item in state["candidates"]
                if item.candidate_id == state["selected_candidate_id"]
            )
        )
        if submission.participant_id not in allowed_ids:
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_CONSENT", "Only an actual attendee may consent."),
            }
        try:
            _check_current_revision(snapshot, tools)
        except StaleInputRevision:
            return {"status": AgentStatus.STALE, "candidates": []}
        merged = dict(state.get("consent_by_attendee_id", {}))
        merged[submission.participant_id] = submission.decision.value
        return {
            "consent_by_attendee_id": merged,
            "consent_declined": any(value == "DISAGREE" for value in merged.values()),
        }

    def route_consents(state: AgentState) -> str:
        if state.get("consent_declined"):
            return "end"
        attendee_ids = set(
            next(
                item.attendee_ids for item in state["candidates"]
                if item.candidate_id == state["selected_candidate_id"]
            )
        )
        consented = {
            participant_id
            for participant_id, decision in state.get("consent_by_attendee_id", {}).items()
            if decision == "AGREE"
        }
        return "await_approval" if attendee_ids <= consented else "collect_consents"

    def await_host_approval(state: AgentState) -> dict[str, Any]:
        candidate = next(
            item for item in state["candidates"]
            if item.candidate_id == state["selected_candidate_id"]
        )
        response = interrupt(
            {
                "kind": "host_approval",
                "candidateId": candidate.candidate_id,
                "inputRevision": candidate.source_revision,
                "consentRound": state["snapshot"].consent_round,
                "organizerId": next(
                    p.participant_id
                    for p in state["snapshot"].participants
                    if p.role == ParticipantRole.ORGANIZER
                ),
            }
        )
        return {"approval_response": response}

    def record_host_decision(state: AgentState) -> dict[str, Any]:
        response = state.get("approval_response")
        snapshot = state["snapshot"]
        candidate_id = state.get("selected_candidate_id")
        candidate = next(
            (item for item in state["candidates"] if item.candidate_id == candidate_id),
            None,
        )
        organizer_id = next(
            p.participant_id
            for p in snapshot.participants
            if p.role == ParticipantRole.ORGANIZER
        )
        if not isinstance(response, dict) or candidate is None:
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_APPROVAL", "A valid host decision is required."),
            }
        try:
            decision = HostApprovalSubmission.model_validate(response)
        except ValidationError:
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_APPROVAL", "The host decision is invalid."),
            }
        if (
            decision.actor_participant_id != organizer_id
            or decision.candidate_id != candidate.candidate_id
            or decision.input_revision != snapshot.input_revision
            or decision.consent_round != snapshot.consent_round
        ):
            return {
                "status": AgentStatus.ERROR,
                "error": _error("INVALID_APPROVAL", "The host decision does not match the current run."),
            }
        try:
            _check_current_revision(snapshot, tools)
        except StaleInputRevision:
            return {"status": AgentStatus.STALE, "candidates": []}
        return {
            "status": AgentStatus.AWAITING_APPROVAL,
            "approval_decision": (
                "APPROVED"
                if decision.decision.value == "APPROVE"
                else "REJECTED"
            ),
            "meeting_finalized": False,
        }

    builder.add_node("load_snapshot", load_snapshot)
    builder.add_node("classify_readiness", classify_readiness)
    builder.add_node("solve_all", solve_all)
    builder.add_node("stale_after_all", stale_after_all)
    builder.add_node("all_solver_error", all_solver_error)
    builder.add_node("validate_all", validate_all)
    builder.add_node("solve_partial", solve_partial)
    builder.add_node("validate_partial", validate_partial)
    builder.add_node("no_schedule", no_schedule)
    builder.add_node("partial_solver_error", partial_solver_error)
    builder.add_node("await_candidate_selection", await_candidate_selection)
    builder.add_node("validate_selection", validate_selection)
    builder.add_node("collect_consents", collect_consents)
    builder.add_node("record_consents", record_consents)
    builder.add_node("await_host_approval", await_host_approval)
    builder.add_node("record_host_decision", record_host_decision)

    builder.add_edge(START, "load_snapshot")
    builder.add_edge("load_snapshot", "classify_readiness")
    builder.add_conditional_edges(
        "classify_readiness",
        route_readiness,
        {"solve_all": "solve_all", "end": END},
    )
    builder.add_conditional_edges(
        "solve_all",
        route_all,
        {
            "stale": "stale_after_all",
            "cancelled": "all_solver_error",
            "validate_all": "validate_all",
            "solve_partial": "solve_partial",
            "all_solver_error": "all_solver_error",
        },
    )
    builder.add_edge("stale_after_all", END)
    builder.add_conditional_edges(
        "validate_all",
        route_validated,
        {"await_selection": "await_candidate_selection", "end": END},
    )
    builder.add_conditional_edges(
        "solve_partial",
        route_partial,
        {
            "stale": "stale_after_all",
            "cancelled": "partial_solver_error",
            "validate_partial": "validate_partial",
            "no_schedule": "no_schedule",
            "partial_solver_error": "partial_solver_error",
        },
    )
    builder.add_conditional_edges(
        "validate_partial",
        route_validated,
        {"await_selection": "await_candidate_selection", "end": END},
    )
    for node in ("all_solver_error", "no_schedule", "partial_solver_error"):
        builder.add_edge(node, END)
    builder.add_edge("await_candidate_selection", "validate_selection")
    builder.add_conditional_edges(
        "validate_selection",
        route_selection,
        {"collect_consents": "collect_consents", "end": END},
    )
    builder.add_edge("collect_consents", "record_consents")
    builder.add_conditional_edges(
        "record_consents",
        route_consents,
        {"collect_consents": "collect_consents", "await_approval": "await_host_approval", "end": END},
    )
    builder.add_edge("await_host_approval", "record_host_decision")
    builder.add_edge("record_host_decision", END)
    return builder.compile(checkpointer=checkpointer)


@contextmanager
def open_local_graph(
    tools: SolverAdapter, checkpoint_path: str | Path
) -> Iterator[Any]:
    """Open a SQLite-backed local graph; checkpoint identifiers stay internal."""
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    connection = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
    try:
        checkpointer = SqliteSaver(
            connection,
            serde=JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_TYPES),
        )
        checkpointer.setup()
        yield build_agent_graph(tools, checkpointer=checkpointer)
    finally:
        connection.close()
