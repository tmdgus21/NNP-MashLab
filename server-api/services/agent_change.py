"""Natural-language change proposals: propose -> confirm -> apply -> recompute.

Trust boundaries
- Qwen only extracts intent through read-only tools on a detached snapshot; the
  Proposal Validator (potato_agent.qwen_proposals) turns that into a proposal.
  Qwen never touches the DB and never approves or finalizes anything.
- No DB session is held during the Qwen call. Reading the snapshot and saving
  the proposal are separate short transactions; the save re-checks the revision.
- Creating a proposal never changes meeting input. Only an explicit approval by
  the requester does, in ONE transaction that: locks the room, re-validates the
  proposal on a fresh snapshot, applies it to the authoritative data (room
  settings / the requester's own availability), bumps the input revision,
  marks the previous Runs STALE, and queues a new Run (CP-SAT recompute by the
  existing Worker). Previous candidates, consents and approvals stay on the
  STALE Runs as history and can never be resumed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.agent import AgentChangeProposal, AgentRun
from db_v21.models.condition import ConditionAvailableSlot, ConditionSubmission
from db_v21.models.room import Room, RoomMember
from potato_agent.llama_cpp import LlamaCppError, build_proposal_agent
from potato_agent.models import MeetingSnapshot
from potato_agent.qwen_proposals import (
    LocalProposalApprovalAdapter,
    ProposalActor,
    ProposalStatus,
    ProposalValidationError,
    RescheduleProposal,
    SetPersonalAvailabilityChange,
)
from services.agent_run import RoomActor, authorize_room_member, start_agent_run
from services.meeting_domain import agent_final_exists, supersede_open_runs
from services.meeting_snapshot import build_meeting_snapshot

SessionFactory = Callable[[], Session]
SEOUL = ZoneInfo("Asia/Seoul")
MAX_REQUEST_CHARS = 1000

# Replaceable in tests; default talks to the loopback test endpoint only
# (LlamaCppClient rejects non-loopback hosts and port 8080).
agent_factory: Callable[[MeetingSnapshot], Any] = build_proposal_agent


class ChangeError(Exception):
    code = "AGENT_CHANGE_ERROR"
    status_code = 409


class InvalidChangeRequestError(ChangeError):
    code = "INVALID_CHANGE_REQUEST"
    status_code = 422


class InvalidProposalError(ChangeError):
    status_code = 422

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class QwenUnavailableError(ChangeError):
    code = "QWEN_UNAVAILABLE"
    status_code = 503


class IdempotencyKeyReusedError(ChangeError):
    code = "IDEMPOTENCY_KEY_REUSED"


class ProposalNotFoundError(ChangeError):
    code = "PROPOSAL_NOT_FOUND"
    status_code = 404


class ProposalForbiddenError(ChangeError):
    code = "PROPOSAL_FORBIDDEN"
    status_code = 403


class ProposalNotApprovableError(ChangeError):
    code = "PROPOSAL_NOT_APPROVABLE"


class StaleProposalError(ChangeError):
    code = "STALE_PROPOSAL"


class RoomNotMutableError(ChangeError):
    """Mirrors /v1: a finalized, cancelled or deleted room accepts no input change."""

    code = "ROOM_NOT_MUTABLE"


class RoundAlreadyFinalizedError(ChangeError):
    """Re-adjustment after a final result needs an explicit new room round."""

    code = "ROUND_ALREADY_FINALIZED"


class ProposalApplyMismatchError(ChangeError):
    code = "PROPOSAL_APPLY_MISMATCH"
    status_code = 500


@dataclass(frozen=True)
class ProposalRecord:
    id: str
    room_id: str
    status: str
    base_revision: int
    summary: str
    changes: tuple[dict[str, Any], ...]
    ambiguities: tuple[str, ...]
    requested_by_member_id: str
    resulting_run_id: str | None
    applied_revision: int | None
    created_at: datetime
    decided_at: datetime | None
    changed: bool = True  # False on an idempotent replay


def _today() -> date:
    return datetime.now(SEOUL).date()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _record(row: AgentChangeProposal, *, changed: bool = True) -> ProposalRecord:
    body = row.proposal
    return ProposalRecord(
        id=row.id,
        room_id=row.room_id,
        status=row.status,
        base_revision=row.base_revision,
        summary=body.get("summary", ""),
        changes=tuple(body.get("changes", ())),
        ambiguities=tuple(body.get("ambiguities", ())),
        requested_by_member_id=row.requested_by_member_id,
        resulting_run_id=row.resulting_run_id,
        applied_revision=row.applied_revision,
        created_at=row.created_at,
        decided_at=row.decided_at,
        changed=changed,
    )


def _actor(actor: RoomActor) -> ProposalActor:
    # Participant IDs in the snapshot are account IDs. A member may only ever
    # edit their own availability; the validator enforces the "own" part.
    return ProposalActor(
        participant_id=actor.account_id, can_edit_own_availability=True
    )


def _status_for(proposal: RescheduleProposal) -> str:
    return {
        ProposalStatus.PROPOSED: "PROPOSED",
        ProposalStatus.CLARIFICATION_REQUIRED: "CLARIFICATION_REQUIRED",
        ProposalStatus.REJECTED: "MODEL_REJECTED",
    }[proposal.status]


def _assert_open_for_changes(db: Session, room: Room) -> None:
    if room.progress_status in ("finalized", "cancelled", "deleted"):
        raise RoomNotMutableError("The room no longer accepts input changes.")
    if agent_final_exists(db, room):
        # The finalized Run is never modified; the host opens a new coordination
        # round (services.coordination_round) before inputs may change again.
        raise RoundAlreadyFinalizedError("This room round already has a final result.")


def _fresh_snapshot(db: Session, room_id: str) -> MeetingSnapshot:
    return build_meeting_snapshot(
        db,
        room_id=room_id,
        agent_session_id=str(uuid4()),
        run_id=str(uuid4()),
        consent_round=1,
    )


# ---------------------------------------------------------------- propose

def create_change_proposal(
    session_factory: SessionFactory,
    *,
    room_id: str,
    actor_account_id: str,
    idempotency_key: str,
    request_text: str,
    today: date | None = None,
) -> ProposalRecord:
    text = (request_text or "").strip()
    if not text or len(text) > MAX_REQUEST_CHARS:
        raise InvalidChangeRequestError(
            f"The request must be 1 to {MAX_REQUEST_CHARS} characters."
        )
    if (
        not isinstance(idempotency_key, str)
        or not idempotency_key.strip()
        or len(idempotency_key) > 200
    ):
        raise InvalidChangeRequestError("Idempotency-Key must be 1 to 200 characters.")
    key_hash, request_hash = _hash(idempotency_key), _hash(text)
    today = today or _today()

    # 1) short read transaction: authorize, replay check, detached snapshot
    with session_factory() as db:
        with db.begin():
            actor = authorize_room_member(
                db, room_id=room_id, actor_account_id=actor_account_id
            )
            existing = _find_by_key(db, room_id, actor.room_member_id, key_hash)
            if existing is not None:
                return _replay(existing, request_hash)
            _assert_open_for_changes(
                db, db.scalar(select(Room).where(Room.id == room_id))
            )
            snapshot = _fresh_snapshot(db, room_id)

    # 2) Qwen call with NO database session open
    try:
        proposal = agent_factory(snapshot).propose(
            text, snapshot, _actor(actor), today=today
        )
    except ProposalValidationError as exc:
        raise InvalidProposalError(exc.code, str(exc)) from exc
    except LlamaCppError as exc:
        raise QwenUnavailableError(f"Qwen request failed: {exc.code}") from exc

    # 3) short write transaction: re-check the base, then store (input untouched)
    try:
        with session_factory() as db:
            with db.begin():
                room = db.scalar(
                    select(Room)
                    .where(Room.id == room_id, Room.deleted_at.is_(None))
                    .with_for_update()
                )
                if room is None or room.agent_input_revision != snapshot.input_revision:
                    raise StaleProposalError(
                        "The meeting changed while the request was being interpreted."
                    )
                row = AgentChangeProposal(
                    room_id=room_id,
                    requested_by_member_id=actor.room_member_id,
                    idempotency_key_hash=key_hash,
                    request_hash=request_hash,
                    request_text=text,
                    base_revision=snapshot.input_revision,
                    base_snapshot_hash=snapshot.input_snapshot_hash,
                    proposal=json.loads(proposal.model_dump_json()),
                    status=_status_for(proposal),
                )
                db.add(row)
                db.flush()
                return _record(row)
    except IntegrityError:  # concurrent same-key request won the insert
        with session_factory() as db:
            with db.begin():
                existing = _find_by_key(db, room_id, actor.room_member_id, key_hash)
                if existing is None:
                    raise
                return _replay(existing, request_hash)


def _find_by_key(db, room_id, member_id, key_hash):
    return db.scalar(
        select(AgentChangeProposal).where(
            AgentChangeProposal.room_id == room_id,
            AgentChangeProposal.requested_by_member_id == member_id,
            AgentChangeProposal.idempotency_key_hash == key_hash,
        )
    )


def _replay(row: AgentChangeProposal, request_hash: str) -> ProposalRecord:
    if row.request_hash != request_hash:
        raise IdempotencyKeyReusedError("Idempotency-Key was used with a different request.")
    return _record(row, changed=False)


def get_change_proposal(
    session_factory: SessionFactory, *, room_id: str, proposal_id: str, actor_account_id: str
) -> ProposalRecord:
    with session_factory() as db:
        actor = authorize_room_member(db, room_id=room_id, actor_account_id=actor_account_id)
        row = _load(db, room_id, proposal_id)
        if row.requested_by_member_id != actor.room_member_id and not actor.is_host:
            raise ProposalForbiddenError("Only the requester or the host may view a proposal.")
        return _record(row, changed=False)


def _load(db: Session, room_id: str, proposal_id: str, *, lock: bool = False):
    query = select(AgentChangeProposal).where(
        AgentChangeProposal.id == proposal_id, AgentChangeProposal.room_id == room_id
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise ProposalNotFoundError("Proposal does not exist.")
    return row


# ---------------------------------------------------------------- reject

def reject_change_proposal(
    session_factory: SessionFactory, *, room_id: str, proposal_id: str, actor_account_id: str
) -> ProposalRecord:
    with session_factory() as db:
        with db.begin():
            actor = authorize_room_member(db, room_id=room_id, actor_account_id=actor_account_id)
            row = _load(db, room_id, proposal_id, lock=True)
            if row.requested_by_member_id != actor.room_member_id and not actor.is_host:
                raise ProposalForbiddenError("Only the requester or the host may reject.")
            if row.status == "REJECTED":
                return _record(row, changed=False)
            if row.status not in ("PROPOSED", "CLARIFICATION_REQUIRED", "MODEL_REJECTED"):
                raise ProposalNotApprovableError(f"A {row.status} proposal cannot be rejected.")
            row.status = "REJECTED"
            row.decided_by_member_id = actor.room_member_id
            row.decided_at = now()
            return _record(row)


# --------------------------------------------------------------- approve

def approve_change_proposal(
    session_factory: SessionFactory,
    *,
    room_id: str,
    proposal_id: str,
    actor_account_id: str,
    today: date | None = None,
) -> ProposalRecord:
    today = today or _today()
    stale_reason: str | None = None
    result: ProposalRecord | None = None
    with session_factory() as db:
        with db.begin():
            room = db.scalar(
                select(Room)
                .where(Room.id == room_id, Room.deleted_at.is_(None))
                .with_for_update()
            )
            actor = authorize_room_member(db, room_id=room_id, actor_account_id=actor_account_id)
            row = _load(db, room_id, proposal_id, lock=True)
            if row.requested_by_member_id != actor.room_member_id:
                raise ProposalForbiddenError("Only the requester may approve their proposal.")
            if row.status == "APPLIED":
                return _record(row, changed=False)  # duplicate approval
            if row.status != "PROPOSED":
                raise ProposalNotApprovableError(f"A {row.status} proposal cannot be approved.")

            _assert_open_for_changes(db, room)
            snapshot = _fresh_snapshot(db, room_id)
            if (
                room.agent_input_revision != row.base_revision
                or snapshot.input_snapshot_hash != row.base_snapshot_hash
            ):
                row.status = "SUPERSEDED"
                row.decided_at = now()
                stale_reason = "The meeting changed after this proposal was made."
            else:
                result = _apply(
                    db, room, row, actor, snapshot, today=today
                )
    if stale_reason:  # raised after commit so SUPERSEDED persists
        raise StaleProposalError(stale_reason)
    assert result is not None
    return result


def _apply(
    db: Session,
    room: Room,
    row: AgentChangeProposal,
    actor: RoomActor,
    snapshot: MeetingSnapshot,
    *,
    today: date,
) -> ProposalRecord:
    proposal = RescheduleProposal.model_validate_json(json.dumps(row.proposal))
    try:
        # Re-runs the Validator (permissions included) on the fresh snapshot.
        updated = LocalProposalApprovalAdapter().approve(
            snapshot, _actor(actor), proposal, today=today
        )
    except ProposalValidationError as exc:
        raise InvalidProposalError(exc.code, str(exc)) from exc

    _write_constraints(room, proposal, updated)
    _write_availability(db, room, proposal, updated)
    room.agent_input_revision = snapshot.input_revision + 1
    room.revision = room.revision + 1
    db.flush()

    rebuilt = _fresh_snapshot(db, room.id)
    _assert_matches(rebuilt, updated, expected_revision=snapshot.input_revision + 1)

    # Same transaction as the input change: no window where the old Runs are
    # still decidable against the new input.
    supersede_open_runs(db, room.id, "Superseded by an approved change proposal.")
    new_run = start_agent_run(
        db,
        room_id=room.id,
        actor_account_id=actor.account_id,
        idempotency_key=f"change-proposal:{row.id}",
        request={"expectedInputRevision": snapshot.input_revision + 1},
    )
    claimed = db.execute(
        update(AgentChangeProposal)
        .where(AgentChangeProposal.id == row.id, AgentChangeProposal.status == "PROPOSED")
        .values(
            status="APPLIED",
            decided_by_member_id=actor.room_member_id,
            decided_at=now(),
            applied_revision=snapshot.input_revision + 1,
            resulting_run_id=new_run.run_id,
        )
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:  # lost a race without row locks: roll everything back
        raise ProposalNotApprovableError("The proposal was decided concurrently.")
    db.refresh(row)
    return _record(row)


def _write_constraints(room: Room, proposal: RescheduleProposal, updated: MeetingSnapshot) -> None:
    if all(isinstance(change, SetPersonalAvailabilityChange) for change in proposal.changes):
        return
    settings = json.loads(json.dumps(room.meeting_settings))  # fresh object: JSON change tracking
    coordination = settings["coordination"]
    coordination["durationMinutes"] = updated.duration_minutes
    coordination["excludedDates"] = [d.isoformat() for d in sorted(updated.excluded_dates)]
    coordination["requiredStartMinutesByDate"] = {
        d.isoformat(): m for d, m in sorted(updated.required_start_minutes_by_date.items())
    }
    coordination["absoluteTimeWindows"] = [
        {"date": w.date.isoformat(), "startMinute": w.start_minute, "endMinute": w.end_minute}
        for w in sorted(
            updated.absolute_time_windows, key=lambda w: (w.date, w.start_minute, w.end_minute)
        )
    ]
    room.meeting_settings = settings


def _write_availability(
    db: Session, room: Room, proposal: RescheduleProposal, updated: MeetingSnapshot
) -> None:
    participant_ids = sorted(
        {c.participant_id for c in proposal.changes if isinstance(c, SetPersonalAvailabilityChange)}
    )
    for participant_id in participant_ids:
        member = db.scalar(
            select(RoomMember).where(
                RoomMember.room_id == room.id,
                RoomMember.account_id == participant_id,
                RoomMember.membership_status == "ACTIVE",
            )
        )
        latest = db.scalar(
            select(ConditionSubmission)
            .where(ConditionSubmission.room_member_id == member.id)
            .order_by(ConditionSubmission.version.desc())
            .limit(1)
        )
        submission = ConditionSubmission(
            room_member_id=member.id,
            version=(latest.version if latest else 0) + 1,
            confirmed=dict(latest.confirmed) if latest else {},
            ai_draft_id=None,
            submitted_at=now(),
        )
        db.add(submission)
        db.flush()
        for slot in updated.availability_by_participant_id[participant_id].slots:
            midnight = datetime.combine(slot.date, time.min, tzinfo=SEOUL)
            db.add(
                ConditionAvailableSlot(
                    condition_submission_id=submission.id,
                    starts_at=midnight + timedelta(minutes=slot.start_minute),
                    ends_at=midnight + timedelta(minutes=slot.end_minute),
                )
            )


def _windows(snapshot: MeetingSnapshot) -> set[tuple[date, int, int]]:
    return {(w.date, w.start_minute, w.end_minute) for w in snapshot.absolute_time_windows}


def _covered(submission) -> set[tuple[date, int]]:
    return {
        (slot.date, minute)
        for slot in submission.slots
        for minute in range(slot.start_minute, slot.end_minute)
    }


def _assert_matches(rebuilt: MeetingSnapshot, updated: MeetingSnapshot, *, expected_revision: int) -> None:
    """The DB-derived snapshot must equal what the Validator approved."""
    same = (
        rebuilt.input_revision == expected_revision
        and rebuilt.duration_minutes == updated.duration_minutes
        and set(rebuilt.dates) == set(updated.dates)
        and set(rebuilt.excluded_dates) == set(updated.excluded_dates)
        and rebuilt.required_start_minutes_by_date == updated.required_start_minutes_by_date
        and _windows(rebuilt) == _windows(updated)
        and set(rebuilt.availability_by_participant_id) == set(updated.availability_by_participant_id)
        and all(
            _covered(rebuilt.availability_by_participant_id[pid]) == _covered(sub)
            for pid, sub in updated.availability_by_participant_id.items()
        )
    )
    if not same:
        raise ProposalApplyMismatchError(
            "Applied data does not match the approved proposal; nothing was changed."
        )
