"""Candidate selection, consent, approval and finalization persistence.

The database is authoritative. Every command runs in one short transaction that
locks the Run row, re-checks permission, Run status, meeting revision/hash and
the candidate/round, applies the change and bumps ``decision_version``. The
graph checkpoint is then rebuilt from the DB (``sync_run_graph``): a failed
rebuild never loses or reverses a committed command, and any later call
re-drives it. Cross-process exclusion for the rebuild is a lease claimed with a
single conditional UPDATE (compare-and-set), not an in-process lock.

Policies preserved: no automatic absence for non-respondents (consent stays
NULL), only the candidate's ATTENDING members may consent, approval needs all
of them to AGREE, and approval is separate from finalization. Nothing here
decides anything on behalf of the AI.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.agent import AgentCandidate, AgentCandidateMember, AgentRun
from db_v21.models.room import Room, RoomMember
from potato_agent.checkpoint import (
    CheckpointError,
    latest_checkpoint_id,
    resume_pending,
)
from potato_agent.graph import build_agent_graph
from services.checkpoint_lease import claim_lease, release_lease
from services.agent_run import (
    RoomActor,
    authorize_room_host,
    authorize_room_member,
)
from services.agent_solver import (
    AgentSnapshotRevalidationError,
    V21CurrentSnapshotProvider,
    _RunSolverAdapter,
)
from services.agent_worker import AgentRunNotFoundError, _clear_lease, _run_result
from services.meeting_snapshot import (
    RoomNotFoundError,
    SnapshotBuildError,
    build_meeting_snapshot,
)

logger = logging.getLogger("agent_decision")
SessionFactory = Callable[[], Session]

_DECIDABLE = frozenset({"ALL_AVAILABLE", "PARTIAL_ALTERNATIVE", "AWAITING_APPROVAL"})


class DecisionError(Exception):
    code = "AGENT_DECISION_ERROR"
    status_code = 409


class RunNotDecidableError(DecisionError):
    code = "RUN_NOT_DECIDABLE"


class StaleDecisionError(DecisionError):
    code = "STALE_AGENT_RUN"


class VersionConflictError(DecisionError):
    code = "DECISION_VERSION_CONFLICT"


class UnknownCandidateError(DecisionError):
    code = "CANDIDATE_NOT_FOUND"
    status_code = 404


class CandidateMismatchError(DecisionError):
    code = "CANDIDATE_MISMATCH"


class NoSelectionError(DecisionError):
    code = "NO_CANDIDATE_SELECTED"


class NotAnAttendeeError(DecisionError):
    code = "NOT_AN_ATTENDEE"
    status_code = 403


class ConsentLockedError(DecisionError):
    code = "CONSENT_LOCKED"


class ApprovalNotPendingError(DecisionError):
    code = "APPROVAL_NOT_PENDING"


class ApprovalRequiredError(DecisionError):
    code = "APPROVAL_REQUIRED"


class AlreadyFinalizedError(DecisionError):
    code = "ALREADY_FINALIZED"


class RoundAlreadyFinalizedError(DecisionError):
    """Another Run already holds this room round's final result."""

    code = "ROUND_ALREADY_FINALIZED"


class RoleAssignmentFinalizedError(DecisionError):
    """The /v1 role assignment already finalized this room; the Agent must not
    produce a second, conflicting final result for it."""

    code = "ROOM_FINALIZED_BY_ROLE_ASSIGNMENT"


class RoomNotActiveError(DecisionError):
    code = "ROOM_NOT_ACTIVE"


@dataclass(frozen=True)
class AttendeeState:
    room_member_id: str
    consent_status: str | None


@dataclass(frozen=True)
class DecisionState:
    run_id: str
    status: str
    approval_status: str
    selected_candidate_id: str | None
    consent_round: int | None
    decision_version: int
    attendees: tuple[AttendeeState, ...]
    all_agreed: bool
    finalized: bool
    graph_sync: str


@dataclass(frozen=True)
class DecisionResult:
    state: DecisionState
    changed: bool


# ---------------------------------------------------------------- reads

def _active_round(db: Session, row: AgentRun) -> int | None:
    if not row.selected_candidate_id:
        return None
    return db.scalar(
        select(func.max(AgentCandidateMember.consent_round)).where(
            AgentCandidateMember.candidate_id == row.selected_candidate_id
        )
    )


def _attendees(db: Session, row: AgentRun) -> list[AgentCandidateMember]:
    round_ = _active_round(db, row)
    if round_ is None:
        return []
    return list(
        db.scalars(
            select(AgentCandidateMember)
            .where(
                AgentCandidateMember.candidate_id == row.selected_candidate_id,
                AgentCandidateMember.consent_round == round_,
                AgentCandidateMember.participation_status == "ATTENDING",
            )
            .order_by(AgentCandidateMember.room_member_id)
        )
    )


def _graph_sync_label(row: AgentRun) -> str:
    if not row.base_checkpoint_ref:
        return "NOT_APPLICABLE"
    return "SYNCED" if row.graph_synced_version >= row.decision_version else "PENDING"


def _state(db: Session, row: AgentRun) -> DecisionState:
    attendees = _attendees(db, row)
    return DecisionState(
        run_id=row.id,
        status=row.status,
        approval_status=row.approval_status,
        selected_candidate_id=row.selected_candidate_id,
        consent_round=_active_round(db, row),
        decision_version=row.decision_version,
        attendees=tuple(
            AttendeeState(item.room_member_id, item.consent_status) for item in attendees
        ),
        all_agreed=bool(attendees) and all(i.consent_status == "AGREE" for i in attendees),
        finalized=row.finalized_at is not None,
        graph_sync=_graph_sync_label(row),
    )


def get_decision_state(
    session_factory: SessionFactory, *, run_id: str, room_id: str, actor_account_id: str
) -> DecisionState:
    with session_factory() as db:
        authorize_room_member(db, room_id=room_id, actor_account_id=actor_account_id)
        row = db.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.room_id == room_id)
        )
        if row is None:
            raise AgentRunNotFoundError("Agent Run does not exist.")
        return _state(db, row)


# ------------------------------------------------------------- commands

def _revalidate(db: Session, row: AgentRun) -> bool:
    """True when the live meeting still matches the Run's immutable input."""
    try:
        current = build_meeting_snapshot(
            db,
            room_id=row.room_id,
            agent_session_id=row.agent_session_id,
            run_id=row.id,
            consent_round=row.consent_round,
        )
    except RoomNotFoundError:
        return False
    except SnapshotBuildError as exc:
        raise AgentSnapshotRevalidationError(
            "The current meeting snapshot could not be verified."
        ) from exc
    return (
        current.input_revision == row.source_revision
        and current.input_snapshot_hash == row.input_snapshot_hash
    )


def _check_version(row: AgentRun, expected: int | None) -> None:
    if expected is not None and expected != row.decision_version:
        raise VersionConflictError("The decision state changed; reload and retry.")


def _recompute(db: Session, row: AgentRun) -> None:
    """Derive Run status/approval from the active round's consents."""
    if row.approval_status in ("APPROVED", "REJECTED"):
        return
    attendees = _attendees(db, row)
    if attendees and all(item.consent_status == "AGREE" for item in attendees):
        row.status = "AWAITING_APPROVAL"
        row.approval_status = "PENDING"
        return
    candidate = db.get(AgentCandidate, row.selected_candidate_id)
    row.status = candidate.candidate_type
    row.approval_status = (
        "SUPERSEDED" if row.approval_status == "SUPERSEDED" else "NOT_REQUESTED"
    )


def _run_command(
    session_factory: SessionFactory,
    *,
    run_id: str,
    room_id: str,
    actor_account_id: str,
    host_only: bool,
    mutate: Callable[[Session, AgentRun, RoomActor], bool],
    allow_finalized: bool = False,
) -> bool:
    stale = False
    changed = False
    with session_factory() as db:
        with db.begin():
            # Lock order is always room -> run (the change-proposal approval and
            # start_agent_run lock the room first), so input changes, consent,
            # approval and finalization of one room are serialized and cannot
            # deadlock. A missing room falls through to authorize's typed error.
            room = db.scalar(
                select(Room)
                .where(Room.id == room_id, Room.deleted_at.is_(None))
                .with_for_update()
            )
            row = db.scalar(
                select(AgentRun)
                .where(AgentRun.id == run_id, AgentRun.room_id == room_id)
                .with_for_update()
            )
            if row is None:
                raise AgentRunNotFoundError("Agent Run does not exist.")
            authorize = authorize_room_host if host_only else authorize_room_member
            actor = authorize(db, room_id=room_id, actor_account_id=actor_account_id)
            if room.progress_status in ("cancelled", "deleted"):
                raise RoomNotActiveError("The room is cancelled or deleted.")
            if (
                row.status not in _DECIDABLE
                or row.cancel_requested_at is not None
                or row.worker_id is not None
            ):
                raise RunNotDecidableError(f"Run in status {row.status} is not decidable.")
            if row.finalized_at is not None and not allow_finalized:
                raise AlreadyFinalizedError("The Run is already finalized.")
            if not _revalidate(db, row):
                row.status = "STALE"
                row.error_code = "STALE_AGENT_RUN"
                row.error_detail = "The meeting changed before the decision."
                row.completed_at = now()
                _clear_lease(row)
                stale = True
            else:
                changed = mutate(db, row, actor)
                if changed:
                    row.decision_version += 1
    if stale:  # raised after commit so STALE persists
        raise StaleDecisionError("The meeting changed; this Run can no longer be decided.")
    return changed


def select_candidate(
    session_factory: SessionFactory,
    checkpointer,
    *,
    run_id: str,
    room_id: str,
    actor_account_id: str,
    candidate_id: str,
    expected_version: int | None = None,
) -> DecisionResult:
    """Host-only. Opens a new consent round; earlier consents stop counting."""

    def mutate(db: Session, row: AgentRun, actor: RoomActor) -> bool:
        _check_version(row, expected_version)
        candidate = db.scalar(
            select(AgentCandidate).where(
                AgentCandidate.id == candidate_id, AgentCandidate.run_id == row.id
            )
        )
        if candidate is None:
            raise UnknownCandidateError("Unknown candidate for this Run.")
        if (
            not candidate.verified
            or not candidate.graph_candidate_id
            or candidate.source_revision != row.source_revision
            or candidate.source_snapshot_hash != row.input_snapshot_hash
        ):
            raise CandidateMismatchError("Candidate does not match the Run input.")
        if row.selected_candidate_id is None:
            new_round = row.consent_round
        else:
            new_round = (
                db.scalar(
                    select(func.max(AgentCandidateMember.consent_round))
                    .join(AgentCandidate, AgentCandidate.id == AgentCandidateMember.candidate_id)
                    .where(AgentCandidate.run_id == row.id)
                )
                + 1
            )
        has_rows = db.scalar(
            select(AgentCandidateMember.candidate_id).where(
                AgentCandidateMember.candidate_id == candidate.id,
                AgentCandidateMember.consent_round == new_round,
            )
        )
        if has_rows is None:
            latest = db.scalar(
                select(func.max(AgentCandidateMember.consent_round)).where(
                    AgentCandidateMember.candidate_id == candidate.id
                )
            )
            for member in list(
                db.scalars(
                    select(AgentCandidateMember).where(
                        AgentCandidateMember.candidate_id == candidate.id,
                        AgentCandidateMember.consent_round == latest,
                    )
                )
            ):
                db.add(
                    AgentCandidateMember(
                        candidate_id=candidate.id,
                        room_member_id=member.room_member_id,
                        consent_round=new_round,
                        participation_status=member.participation_status,
                        consent_status=None,
                        consented_at=None,
                        consent_note=None,
                    )
                )
        row.selected_candidate_id = candidate.id
        row.selected_at = now()
        row.approval_by_member_id = None
        row.approval_at = None
        row.approval_status = (
            "SUPERSEDED"
            if row.approval_status in ("APPROVED", "REJECTED", "SUPERSEDED")
            else "NOT_REQUESTED"
        )
        db.flush()
        _recompute(db, row)
        return True

    changed = _run_command(
        session_factory, run_id=run_id, room_id=room_id,
        actor_account_id=actor_account_id, host_only=True, mutate=mutate,
    )
    return _finish(session_factory, checkpointer, run_id, room_id, actor_account_id, changed)


def record_consent(
    session_factory: SessionFactory,
    checkpointer,
    *,
    run_id: str,
    room_id: str,
    actor_account_id: str,
    decision: str,
    expected_version: int | None = None,
) -> DecisionResult:
    """Own consent only. decision: AGREE | DISAGREE | WITHDRAW (back to pending)."""
    targets = {"AGREE": "AGREE", "DISAGREE": "DISAGREE", "WITHDRAW": None}
    if decision not in targets:
        raise DecisionError("Unsupported consent decision.")
    target = targets[decision]

    def mutate(db: Session, row: AgentRun, actor: RoomActor) -> bool:
        if not row.selected_candidate_id:
            raise NoSelectionError("No candidate has been selected.")
        round_ = _active_round(db, row)
        member = db.get(
            AgentCandidateMember,
            (row.selected_candidate_id, actor.room_member_id, round_),
        )
        if member is None or member.participation_status != "ATTENDING":
            raise NotAnAttendeeError("Only an actual attendee of the candidate may respond.")
        if member.consent_status == target:
            return False  # idempotent replay
        if row.approval_status in ("APPROVED", "REJECTED"):
            raise ConsentLockedError("Approval was decided; re-select to change consent.")
        _check_version(row, expected_version)
        member.consent_status = target
        member.consented_at = now() if target else None
        member.consent_note = None
        db.flush()
        _recompute(db, row)
        return True

    changed = _run_command(
        session_factory, run_id=run_id, room_id=room_id,
        actor_account_id=actor_account_id, host_only=False, mutate=mutate,
    )
    return _finish(session_factory, checkpointer, run_id, room_id, actor_account_id, changed)


def decide_approval(
    session_factory: SessionFactory,
    checkpointer,
    *,
    run_id: str,
    room_id: str,
    actor_account_id: str,
    decision: str,
    expected_version: int | None = None,
) -> DecisionResult:
    """Host-only, only after every actual attendee AGREEd. Does not finalize."""
    if decision not in ("APPROVE", "REJECT"):
        raise DecisionError("Unsupported approval decision.")
    target = "APPROVED" if decision == "APPROVE" else "REJECTED"

    def mutate(db: Session, row: AgentRun, actor: RoomActor) -> bool:
        if row.approval_status == target:
            return False  # idempotent replay
        if row.approval_status != "PENDING":
            raise ApprovalNotPendingError("Approval is not pending for this Run.")
        _check_version(row, expected_version)
        attendees = _attendees(db, row)
        if not attendees or any(i.consent_status != "AGREE" for i in attendees):
            raise ApprovalNotPendingError("Every actual attendee must AGREE first.")
        row.approval_status = target
        row.approval_by_member_id = actor.room_member_id
        row.approval_at = now()
        return True

    changed = _run_command(
        session_factory, run_id=run_id, room_id=room_id,
        actor_account_id=actor_account_id, host_only=True, mutate=mutate,
    )
    return _finish(session_factory, checkpointer, run_id, room_id, actor_account_id, changed)


def finalize_meeting(
    session_factory: SessionFactory,
    checkpointer,
    *,
    run_id: str,
    room_id: str,
    actor_account_id: str,
    expected_version: int | None = None,
) -> DecisionResult:
    """Host-only, separate from approval. Persists the finalized marker only."""

    def mutate(db: Session, row: AgentRun, actor: RoomActor) -> bool:
        if row.finalized_at is not None:
            return False  # idempotent replay
        if row.approval_status != "APPROVED":
            raise ApprovalRequiredError("An approved candidate is required to finalize.")
        _check_version(row, expected_version)
        room = db.get(Room, row.room_id)
        if room.progress_status == "finalized":
            raise RoleAssignmentFinalizedError("The room is finalized by /v1 role assignment.")
        coordination_round = room.coordination_round
        holder = db.scalar(
            select(AgentRun.id).where(
                AgentRun.room_id == row.room_id,
                AgentRun.finalized_at.is_not(None),
                AgentRun.finalized_room_round == coordination_round,
                AgentRun.id != row.id,
            )
        )
        if holder is not None:
            raise RoundAlreadyFinalizedError("This room round already has a final result.")
        row.finalized_at = now()
        row.finalized_by_member_id = actor.room_member_id
        row.finalized_room_round = coordination_round
        try:
            db.flush()  # the partial unique index is the last line of defence
        except IntegrityError as exc:
            raise RoundAlreadyFinalizedError(
                "This room round already has a final result."
            ) from exc
        return True

    changed = _run_command(
        session_factory, run_id=run_id, room_id=room_id,
        actor_account_id=actor_account_id, host_only=True, mutate=mutate,
        allow_finalized=True,
    )
    return _finish(session_factory, checkpointer, run_id, room_id, actor_account_id, changed)


def _finish(session_factory, checkpointer, run_id, room_id, actor_account_id, changed):
    try:
        sync_run_graph(session_factory, checkpointer, run_id=run_id)
    except Exception:  # the committed DB command must never be lost to a sync error
        logger.exception("graph sync failed for run %s; left PENDING", run_id)
    return DecisionResult(
        state=get_decision_state(
            session_factory, run_id=run_id, room_id=room_id,
            actor_account_id=actor_account_id,
        ),
        changed=changed,
    )


# ----------------------------------------------------------- graph sync

def _claim_sync(session_factory: SessionFactory, run_id: str, owner: str) -> bool:
    return claim_lease(
        session_factory,
        run_id,
        owner,
        extra_where=(
            # stale/cancelled/failed Runs are never rebuilt or resumed
            AgentRun.status.in_(_DECIDABLE),
            AgentRun.base_checkpoint_ref.is_not(None),
            AgentRun.graph_synced_version < AgentRun.decision_version,
        ),
    )


def _release_sync(
    session_factory: SessionFactory, run_id: str, owner: str, *, synced: int | None, ref: str | None
) -> bool:
    values = {} if synced is None else {"graph_synced_version": synced, "checkpoint_ref": ref}
    return release_lease(session_factory, run_id, owner, **values)


def _desired_graph_state(db: Session, row: AgentRun):
    candidate = db.get(AgentCandidate, row.selected_candidate_id)
    round_ = _active_round(db, row)
    consents = list(
        db.execute(
            select(RoomMember.account_id, AgentCandidateMember.consent_status)
            .join(RoomMember, RoomMember.id == AgentCandidateMember.room_member_id)
            .where(
                AgentCandidateMember.candidate_id == candidate.id,
                AgentCandidateMember.consent_round == round_,
                AgentCandidateMember.participation_status == "ATTENDING",
                AgentCandidateMember.consent_status.is_not(None),
            )
            .order_by(AgentCandidateMember.consented_at, RoomMember.account_id)
        )
    )
    host_account = db.scalar(
        select(RoomMember.account_id).where(RoomMember.id == row.approval_by_member_id)
    ) if row.approval_by_member_id else None
    return candidate.graph_candidate_id, consents, row.approval_status, host_account


def sync_run_graph(session_factory: SessionFactory, checkpointer, *, run_id: str) -> str:
    """Rebuild the checkpoint from the DB decision state. Idempotent.

    Returns NOT_APPLICABLE | SYNCED | PENDING (another process holds the lease,
    or the rebuild failed and will be retried by the next call).
    """
    if checkpointer is None:
        return "NOT_APPLICABLE"
    owner = str(uuid4())
    for _ in range(3):  # decision_version may advance while rebuilding
        if not _claim_sync(session_factory, run_id, owner):
            with session_factory() as db:
                row = db.get(AgentRun, run_id)
                if row is None or not row.base_checkpoint_ref:
                    return "NOT_APPLICABLE"
                return _graph_sync_label(row)  # SYNCED, or PENDING under another owner
        try:
            with session_factory() as db:
                row = db.get(AgentRun, run_id)
                version = row.decision_version
                thread_id, base_ref = row.checkpoint_thread_id, row.base_checkpoint_ref
                if row.selected_candidate_id:
                    desired = _desired_graph_state(db, row)
                    revision = row.source_revision
                    round_ = row.consent_round
                else:
                    desired = None
                run_result = _run_result(db, row)
            adapter = _RunSolverAdapter(
                run_result,
                V21CurrentSnapshotProvider(session_factory),
                time_limit_seconds=1.0,
                cancellation_event=None,
            )
            graph = build_agent_graph(adapter, checkpointer=checkpointer)
            if desired is not None:
                graph_candidate_id, consents, approval, host_account = desired
                resume_pending(
                    graph, thread_id, expected_kind="candidate_selection",
                    expected_checkpoint_id=None, from_checkpoint_id=base_ref,
                    resume_value={"candidateId": graph_candidate_id, "inputRevision": revision},
                )
                for account_id, consent in consents:
                    resume_pending(
                        graph, thread_id, expected_kind="participant_consents",
                        expected_checkpoint_id=None,
                        resume_value={
                            "participantId": account_id,
                            "candidateId": graph_candidate_id,
                            "inputRevision": revision,
                            "consentRound": round_,
                            "decision": consent,
                        },
                    )
                    if consent == "DISAGREE":
                        break  # the graph ends on a decline
                if approval in ("APPROVED", "REJECTED"):
                    resume_pending(
                        graph, thread_id, expected_kind="host_approval",
                        expected_checkpoint_id=None,
                        resume_value={
                            "actorParticipantId": host_account,
                            "candidateId": graph_candidate_id,
                            "inputRevision": revision,
                            "consentRound": round_,
                            "decision": "APPROVE" if approval == "APPROVED" else "REJECT",
                        },
                    )
            new_ref = latest_checkpoint_id(graph, thread_id)
        except (CheckpointError, Exception):
            logger.exception("graph rebuild failed for run %s", run_id)
            _release_sync(session_factory, run_id, owner, synced=None, ref=None)
            return "PENDING"
        if not _release_sync(session_factory, run_id, owner, synced=version, ref=new_ref):
            return "PENDING"  # lease was lost; whoever holds it will finish
        with session_factory() as db:
            row = db.get(AgentRun, run_id)
            if row.graph_synced_version >= row.decision_version:
                return "SYNCED"
    return "PENDING"


# ------------------------------------------------- canonical final result

@dataclass(frozen=True)
class FinalResult:
    """The Agent's canonical final meeting time for the room's CURRENT round.

    ``finalized=False`` carries no run. rooms.progress_status/lifecycle_status
    are reported for information only: they track the /v1 role-assignment
    finalization and are never written by the Agent flow.
    """

    finalized: bool
    coordination_round: int
    room_progress_status: str
    room_lifecycle_status: str
    current_input_revision: int
    run_id: str | None = None
    candidate_id: str | None = None
    starts_at: object | None = None
    ends_at: object | None = None
    time_zone: str | None = None
    candidate_type: str | None = None
    attendee_member_ids: tuple[str, ...] = ()
    approved_by_member_id: str | None = None
    approved_at: object | None = None
    finalized_by_member_id: str | None = None
    finalized_at: object | None = None
    input_revision: int | None = None
    input_current: bool | None = None


def get_final_result(
    session_factory: SessionFactory, *, room_id: str, actor_account_id: str
) -> FinalResult:
    with session_factory() as db:
        authorize_room_member(db, room_id=room_id, actor_account_id=actor_account_id)
        room = db.scalar(select(Room).where(Room.id == room_id, Room.deleted_at.is_(None)))
        base = dict(
            coordination_round=room.coordination_round,
            room_progress_status=room.progress_status,
            room_lifecycle_status=room.lifecycle_status,
            current_input_revision=room.agent_input_revision,
        )
        row = db.scalar(
            select(AgentRun).where(
                AgentRun.room_id == room_id,
                AgentRun.finalized_at.is_not(None),
                AgentRun.finalized_room_round == room.coordination_round,
            )
        )
        if row is None:
            return FinalResult(finalized=False, **base)
        candidate = db.get(AgentCandidate, row.selected_candidate_id)
        try:
            input_current = _revalidate(db, row)
        except Exception:
            input_current = None  # could not be verified; never claim "current"
        return FinalResult(
            finalized=True,
            run_id=row.id,
            candidate_id=candidate.id,
            starts_at=candidate.starts_at,
            ends_at=candidate.ends_at,
            time_zone=candidate.time_zone,
            candidate_type=candidate.candidate_type,
            attendee_member_ids=tuple(item.room_member_id for item in _attendees(db, row)),
            approved_by_member_id=row.approval_by_member_id,
            approved_at=row.approval_at,
            finalized_by_member_id=row.finalized_by_member_id,
            finalized_at=row.finalized_at,
            input_revision=row.source_revision,
            input_current=input_current,
            **base,
        )
