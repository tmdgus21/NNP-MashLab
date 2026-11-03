"""Guarded resume of a paused Agent Run from its durable checkpoint.

The Agent Run row is authoritative; the checkpoint is only graph-internal state.
Candidates are linked to the checkpoint by the persisted, immutable
``agent_candidates.graph_candidate_id`` (never by time or type). This is the
low-level resume; the production decision flow is services.agent_decision.

Every resume re-checks, against the DB: actor permission, Run status/cancel,
attempt-scoped thread binding, and the current meeting revision and snapshot
hash. It does not persist consent/approval outcomes: those policies are owned
by the existing flows and are intentionally untouched here.
"""
from __future__ import annotations

import threading
from uuid import uuid4
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.agent import AgentCandidate, AgentRun
from potato_agent.checkpoint import (
    CheckpointCorruptError,
    CheckpointMissingError,
    ResumeConflictError,
    latest_checkpoint_id,
    map_checkpoint_errors,
    resume_pending,
    run_thread_id,
    thread_config,
)
from potato_agent.graph import build_agent_graph
from services.agent_run import authorize_room_host, authorize_room_member
from services.checkpoint_lease import claim_lease, release_lease
from services.agent_solver import (
    AgentSnapshotRevalidationError,
    V21CurrentSnapshotProvider,
    _RunSolverAdapter,
)
from services.agent_worker import (
    AgentRunNotFoundError,
    _clear_lease,
    _run_result,
)
from services.meeting_snapshot import (
    RoomNotFoundError,
    SnapshotBuildError,
    build_meeting_snapshot,
)

SessionFactory = Callable[[], Session]

# kind -> (needs host, payload field that must equal the acting account id)
_RESUME_KINDS: dict[str, tuple[bool, str | None]] = {
    "candidate_selection": (False, None),
    "participant_consents": (False, "participantId"),
    "host_approval": (True, "actorParticipantId"),
}
_RESUMABLE_STATUSES = frozenset(
    {"ALL_AVAILABLE", "PARTIAL_ALTERNATIVE", "AWAITING_APPROVAL"}
)


class AgentResumeError(Exception):
    code = "AGENT_RESUME_ERROR"


class InvalidResumeRequestError(AgentResumeError):
    code = "INVALID_RESUME_REQUEST"


class RunNotResumableError(AgentResumeError):
    code = "RUN_NOT_RESUMABLE"


class ResumeManagedByDecisionError(AgentResumeError):
    """The DB decision flow owns this Run's checkpoint; low-level resume is refused."""

    code = "RESUME_MANAGED_BY_DECISION"


class StaleResumeError(AgentResumeError):
    code = "STALE_AGENT_RUN"


@dataclass(frozen=True)
class ResumeOutcome:
    run_id: str
    graph_status: str | None
    next_pause_kind: str | None
    checkpoint_ref: str | None
    approval_decision: str | None
    meeting_finalized: bool


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _run_lock(run_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(run_id, threading.Lock())


def _assert_resumable(row: AgentRun) -> None:
    if (
        row.status not in _RESUMABLE_STATUSES
        or row.cancel_requested_at is not None
        or row.worker_id is not None
    ):
        raise RunNotResumableError(f"Run in status {row.status} cannot be resumed.")


def _prepare(
    session_factory: SessionFactory,
    *,
    run_id: str,
    actor_account_id: str,
    kind: str,
    payload: dict[str, Any],
):
    needs_host, actor_field = _RESUME_KINDS[kind]
    if actor_field is not None and payload.get(actor_field) != actor_account_id:
        raise InvalidResumeRequestError("Payload actor does not match the caller.")
    stale = False
    with session_factory() as db:
        with db.begin():
            row = db.scalar(
                select(AgentRun).where(AgentRun.id == run_id).with_for_update()
            )
            if row is None:
                raise AgentRunNotFoundError("Agent Run does not exist.")
            authorize = authorize_room_host if needs_host else authorize_room_member
            authorize(db, room_id=row.room_id, actor_account_id=actor_account_id)
            _assert_resumable(row)
            if row.decision_version > 0 or row.selected_candidate_id is not None:
                # DB is canonical once decisions exist; a graph-only resume would
                # diverge from it and race the rebuild over checkpoint_ref.
                raise ResumeManagedByDecisionError(
                    "This Run is managed by the decision flow."
                )
            if not row.checkpoint_thread_id or not row.checkpoint_ref:
                raise CheckpointMissingError("Run has no durable checkpoint.")
            if row.checkpoint_thread_id != run_thread_id(row.id, row.attempt_number):
                raise CheckpointCorruptError("Checkpoint thread does not match the Run attempt.")
            if payload.get("inputRevision", row.source_revision) != row.source_revision:
                raise InvalidResumeRequestError("Payload revision does not match the Run.")
            try:
                current = build_meeting_snapshot(
                    db,
                    room_id=row.room_id,
                    agent_session_id=row.agent_session_id,
                    run_id=row.id,
                    consent_round=row.consent_round,
                )
            except RoomNotFoundError:
                current = None
            except SnapshotBuildError as exc:
                raise AgentSnapshotRevalidationError(
                    "The current meeting snapshot could not be verified."
                ) from exc
            if (
                current is None
                or current.input_revision != row.source_revision
                or current.input_snapshot_hash != row.input_snapshot_hash
            ):
                row.status = "STALE"
                row.error_code = "STALE_AGENT_RUN"
                row.error_detail = "The meeting changed before the resume."
                row.completed_at = now()
                _clear_lease(row)
                stale = True
            else:
                run_result = _run_result(db, row)
                graph_candidate_id = None
                if "candidateId" in payload:
                    stored = db.scalar(
                        select(AgentCandidate).where(
                            AgentCandidate.id == payload["candidateId"],
                            AgentCandidate.run_id == row.id,
                        )
                    )
                    if stored is None:
                        raise InvalidResumeRequestError("Unknown candidate for this Run.")
                    if not stored.graph_candidate_id:
                        raise CheckpointCorruptError(
                            "Candidate has no persisted Graph identifier."
                        )
                    graph_candidate_id = stored.graph_candidate_id
                prepared = (
                    run_result,
                    row.checkpoint_thread_id,
                    row.checkpoint_ref,
                    graph_candidate_id,
                )
    if stale:  # raised after commit so the STALE transition persists
        raise StaleResumeError("The meeting changed; this Run can no longer be resumed.")
    return prepared


def _verify_checkpoint_matches_run(graph, thread_id: str, run_result) -> None:
    with map_checkpoint_errors():
        state = graph.get_state(thread_config(thread_id))
    if not (state.config or {}).get("configurable", {}).get("checkpoint_id"):
        raise CheckpointMissingError("No checkpoint exists for this run.")
    values = state.values
    snapshot = values.get("snapshot") if values else None
    if (
        snapshot is None
        or snapshot.run_id != run_result.run_id
        or snapshot.input_snapshot_hash != run_result.input_snapshot_hash
        or snapshot.input_revision != run_result.source_revision
    ):
        raise CheckpointCorruptError("Checkpoint state does not belong to this Run.")


def _commit_checkpoint_ref(
    session_factory: SessionFactory,
    *,
    run_id: str,
    observed: str,
    new_ref: str | None,
    owner: str,
) -> None:
    with session_factory() as db:
        with db.begin():
            row = db.scalar(
                select(AgentRun).where(AgentRun.id == run_id).with_for_update()
            )
            if row is None:
                raise AgentRunNotFoundError("Agent Run does not exist.")
            _assert_resumable(row)
            if row.sync_owner != owner:
                raise ResumeConflictError("The checkpoint lease was lost.")
            if row.decision_version > 0 or row.selected_candidate_id is not None:
                raise ResumeManagedByDecisionError(
                    "A decision was recorded during the resume; the rebuild owns the checkpoint."
                )
            if row.checkpoint_ref != observed:
                raise ResumeConflictError("Another resume already advanced this Run.")
            if new_ref:
                row.checkpoint_ref = new_ref
            row.sync_owner = None
            row.sync_lease_expires_at = None


def resume_agent_run(
    session_factory: SessionFactory,
    checkpointer,
    *,
    run_id: str,
    actor_account_id: str,
    kind: str,
    payload: dict[str, Any],
) -> ResumeOutcome:
    if kind not in _RESUME_KINDS or not isinstance(payload, dict):
        raise InvalidResumeRequestError("Unsupported resume kind or payload.")
    with _run_lock(run_id):
        # The lease comes first: while held, the decision flow cannot rebuild
        # (its claim fails and stays PENDING) and no other resume can write
        # checkpoint_ref. _prepare then re-checks, under the row lock, that no
        # decision exists, so a command that committed before the claim is seen.
        owner = str(uuid4())
        if not claim_lease(session_factory, run_id, owner):
            raise ResumeConflictError("The checkpoint is being modified by another process.")
        try:
            run_result, thread_id, observed_ref, graph_candidate_id = _prepare(
                session_factory,
                run_id=run_id,
                actor_account_id=actor_account_id,
                kind=kind,
                payload=payload,
            )
            adapter = _RunSolverAdapter(
                run_result,
                V21CurrentSnapshotProvider(session_factory),
                time_limit_seconds=1.0,
                cancellation_event=None,
            )
            graph = build_agent_graph(adapter, checkpointer=checkpointer)
            _verify_checkpoint_matches_run(graph, thread_id, run_result)
            if graph_candidate_id is not None:
                payload = {**payload, "candidateId": graph_candidate_id}
            result = resume_pending(
                graph,
                thread_id,
                expected_kind=kind,
                expected_checkpoint_id=observed_ref,
                resume_value=payload,
            )
            new_ref = latest_checkpoint_id(graph, thread_id)
            _commit_checkpoint_ref(
                session_factory,
                run_id=run_id,
                observed=observed_ref,
                new_ref=new_ref,
                owner=owner,
            )
        finally:
            release_lease(session_factory, run_id, owner)  # no-op once committed
    interrupts = result.get("__interrupt__") or []
    status = result.get("status")
    return ResumeOutcome(
        run_id=run_id,
        graph_status=getattr(status, "value", status),
        next_pause_kind=interrupts[0].value.get("kind") if interrupts else None,
        checkpoint_ref=new_ref,
        approval_decision=result.get("approval_decision"),
        meeting_finalized=bool(result.get("meeting_finalized")),
    )
