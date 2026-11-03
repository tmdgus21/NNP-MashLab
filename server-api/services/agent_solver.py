"""Run the Agent Core solver against a detached, persisted Agent Run snapshot."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Protocol

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.orm import Session

from services.agent_run import AgentRunResult
from services.meeting_snapshot import (
    MeetingSnapshot,
    RoomNotFoundError,
    SnapshotBuildError,
    build_meeting_snapshot,
)

from potato_agent.candidate_validator import StaleInputRevision
from potato_agent.checkpoint import (
    CheckpointUnavailableError,
    latest_checkpoint_id,
    map_checkpoint_errors,
)
from potato_agent.graph import AgentStatus, build_agent_graph
from potato_agent.models import Candidate, ReadinessReport, SolverResult, SolverStatus
from potato_agent.ortools_adapter import CpSatSolverAdapter


SessionFactory = Callable[[], Session]


class AgentSolverServiceError(Exception):
    code = "AGENT_SOLVER_ERROR"
    retryable = False


class StaleAgentRunError(AgentSolverServiceError):
    code = "STALE_AGENT_RUN"


class AgentSolverCancelledError(AgentSolverServiceError):
    code = "SOLVER_CANCELLED"


class AgentSolverTimeoutError(AgentSolverServiceError):
    code = "SOLVER_TIMEOUT"
    retryable = True


class AgentSolverUnknownError(AgentSolverServiceError):
    code = "SOLVER_UNKNOWN"
    retryable = True


class AgentCandidateValidationError(AgentSolverServiceError):
    code = "CANDIDATE_VALIDATION_FAILED"


class AgentSolverFailureError(AgentSolverServiceError):
    code = "SOLVER_FAILURE"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code


class AgentSnapshotRevalidationError(AgentSolverServiceError):
    code = "SNAPSHOT_REVALIDATION_FAILED"
    retryable = True


@dataclass(frozen=True)
class AgentSolverOutput:
    run_id: str
    meeting_id: str
    source_revision: int
    input_snapshot_hash: str
    status: AgentStatus
    candidates: tuple[Candidate, ...] = ()
    readiness: ReadinessReport | None = None
    all_solver_status: SolverStatus | None = None
    partial_solver_status: SolverStatus | None = None
    solve_time_seconds: float = 0.0
    checkpoint_thread_id: str | None = None
    checkpoint_ref: str | None = None


class CurrentSnapshotProvider(Protocol):
    def load_current(self, run: AgentRunResult) -> MeetingSnapshot: ...


class V21CurrentSnapshotProvider:
    """Rebuild the source snapshot in a fresh, short-lived v2.1 DB session."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def load_current(self, run: AgentRunResult) -> MeetingSnapshot:
        with self._session_factory() as db:
            return build_meeting_snapshot(
                db,
                room_id=run.meeting_id,
                agent_session_id=run.agent_session_id,
                run_id=run.run_id,
                consent_round=run.snapshot.consent_round,
            )


class _RunSolverAdapter:
    """Expose the detached Run snapshot and fresh source-version checks to Agent Core."""

    def __init__(
        self,
        run: AgentRunResult,
        current_snapshot_provider: CurrentSnapshotProvider,
        *,
        time_limit_seconds: float,
        cancellation_event: threading.Event | None,
    ) -> None:
        self._run = run
        self._snapshot = run.snapshot
        self._current_snapshot_provider = current_snapshot_provider
        self._solver = CpSatSolverAdapter(
            self._snapshot,
            time_limit_seconds=time_limit_seconds,
            revision_provider=self._current_input_revision,
            cancellation_event=cancellation_event,
        )

    def _load_verified_current_snapshot(self, meeting_id: str) -> MeetingSnapshot:
        if meeting_id != self._run.meeting_id:
            raise ValueError("Solver adapter received an unknown meeting.")
        try:
            current = self._current_snapshot_provider.load_current(self._run)
        except RoomNotFoundError as exc:
            raise StaleInputRevision("The meeting no longer exists.") from exc
        except SnapshotBuildError as exc:
            raise AgentSnapshotRevalidationError(
                "The current meeting snapshot could not be verified."
            ) from exc
        if (
            current.input_revision != self._run.source_revision
            or current.input_snapshot_hash != self._run.input_snapshot_hash
        ):
            raise StaleInputRevision(
                "The meeting input revision or snapshot hash changed."
            )
        return current

    def _current_input_revision(self, meeting_id: str) -> int:
        return self._load_verified_current_snapshot(meeting_id).input_revision

    def verify_current_snapshot(self) -> MeetingSnapshot:
        return self._load_verified_current_snapshot(self._run.meeting_id)

    def load_snapshot(self, meeting_id: str) -> MeetingSnapshot:
        if meeting_id != self._run.meeting_id:
            raise ValueError("Solver adapter received an unknown meeting.")
        return self._snapshot

    def current_input_revision(self, meeting_id: str) -> int:
        return self._current_input_revision(meeting_id)

    def solve_all_attendees(self, snapshot: MeetingSnapshot) -> SolverResult:
        return self._solver.solve_all_attendees(snapshot)

    def solve_partial_attendees(
        self, snapshot: MeetingSnapshot, minimum_attendee_count: int
    ) -> SolverResult:
        return self._solver.solve_partial_attendees(snapshot, minimum_attendee_count)


def _validate_run_snapshot(run: AgentRunResult) -> None:
    snapshot = run.snapshot
    if (
        snapshot.meeting_id != run.meeting_id
        or snapshot.run_id != run.run_id
        or snapshot.agent_session_id != run.agent_session_id
        or snapshot.input_revision != run.source_revision
        or snapshot.input_snapshot_hash != run.input_snapshot_hash
    ):
        raise AgentSolverFailureError(
            "Agent Run metadata does not match its immutable snapshot."
        )


def _durable_checkpoint_ref(graph, thread_id: str) -> str | None:
    try:
        return latest_checkpoint_id(graph, thread_id)
    except CheckpointUnavailableError as exc:
        raise AgentSolverFailureError(
            "The checkpoint store is unavailable.", code=exc.code
        ) from exc


def run_agent_solver(
    run: AgentRunResult,
    *,
    session_factory: SessionFactory,
    time_limit_seconds: float = 5.0,
    cancellation_event: threading.Event | None = None,
    expected_status: str = "QUEUED",
    checkpointer=None,
    checkpoint_thread_id: str | None = None,
) -> AgentSolverOutput:
    """Solve a queued Run and return validated candidates without persisting state.

    Each revision/hash verification opens and closes its own DB session. The
    LangGraph and CP-SAT executions only use the detached immutable snapshot.
    """
    _validate_run_snapshot(run)
    if run.status != expected_status or expected_status not in ("QUEUED", "RUNNING"):
        raise AgentSolverFailureError(
            "Agent Run status does not match the solver invocation."
        )
    if time_limit_seconds <= 0:
        raise AgentSolverFailureError("Solver time limit must be greater than zero.")

    provider = V21CurrentSnapshotProvider(session_factory)
    adapter = _RunSolverAdapter(
        run,
        provider,
        time_limit_seconds=time_limit_seconds,
        cancellation_event=cancellation_event,
    )
    durable = checkpointer is not None
    thread_id = checkpoint_thread_id or f"agent-run:{run.run_id}"
    graph = build_agent_graph(
        adapter, checkpointer=checkpointer if durable else MemorySaver()
    )
    try:
        with map_checkpoint_errors(unreadable_is_corrupt=False):
            state = graph.invoke(
                {"meeting_id": run.meeting_id},
                config={"configurable": {"thread_id": thread_id}},
            )
    except CheckpointUnavailableError as exc:
        raise AgentSolverFailureError(
            "The checkpoint store is unavailable.", code=exc.code
        ) from exc
    except StaleInputRevision as exc:
        raise StaleAgentRunError(
            "The meeting changed before the solver could start."
        ) from exc

    try:
        adapter.verify_current_snapshot()
    except StaleInputRevision as exc:
        raise StaleAgentRunError(
            "The meeting changed before validated candidates could be returned."
        ) from exc

    status = state.get("status")
    if status == AgentStatus.STALE:
        raise StaleAgentRunError("The meeting changed while the solver was running.")
    if status == AgentStatus.CANCELLED:
        raise AgentSolverCancelledError("The solver run was cancelled.")
    if status == AgentStatus.ERROR:
        error = state.get("error", {})
        code = error.get("code")
        if code == "SOLVER_TIMEOUT":
            raise AgentSolverTimeoutError(error.get("message", "Solver timed out."))
        if code == "SOLVER_UNKNOWN":
            raise AgentSolverUnknownError(
                error.get("message", "Solver could not establish a result.")
            )
        if code == "CANDIDATE_VALIDATION_FAILED":
            raise AgentCandidateValidationError(
                error.get("message", "Candidate validation failed.")
            )
        raise AgentSolverFailureError(
            error.get("message", "Agent Core solver execution failed."),
            code=code or "SOLVER_FAILURE",
        )
    if status not in (
        AgentStatus.WAITING_FOR_INPUT,
        AgentStatus.NO_FEASIBLE_SCHEDULE,
        AgentStatus.ALL_AVAILABLE,
        AgentStatus.PARTIAL_ALTERNATIVE,
    ):
        raise AgentSolverFailureError("Agent Core returned an unsupported state.")

    candidates = tuple(state.get("candidates", ()))
    if status in (AgentStatus.ALL_AVAILABLE, AgentStatus.PARTIAL_ALTERNATIVE):
        if not candidates or any(not isinstance(item, Candidate) for item in candidates):
            raise AgentCandidateValidationError(
                "Agent Core returned no validated candidates."
            )
    solve_time_seconds = sum(
        result.solve_time_seconds
        for result in (state.get("all_result"), state.get("partial_result"))
        if result is not None
    )
    return AgentSolverOutput(
        run_id=run.run_id,
        meeting_id=run.meeting_id,
        source_revision=run.source_revision,
        input_snapshot_hash=run.input_snapshot_hash,
        status=status,
        candidates=candidates,
        readiness=state.get("readiness"),
        all_solver_status=state.get("all_solver_status"),
        partial_solver_status=state.get("partial_solver_status"),
        solve_time_seconds=solve_time_seconds,
        checkpoint_thread_id=thread_id if durable else None,
        checkpoint_ref=_durable_checkpoint_ref(graph, thread_id) if durable else None,
    )
