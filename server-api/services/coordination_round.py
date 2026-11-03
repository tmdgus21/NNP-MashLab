"""Explicit host action that opens the next Potato Meet coordination round.

Independent of /v1 ``extensions`` and of ``rooms.current_round`` (the /v1
role-plan round). Opening a round:
- keeps ``meeting_settings`` (including ``coordination``) byte-for-byte;
- leaves the finalized Run and every candidate/consent/approval row untouched;
- marks the remaining open Runs STALE, so no consent or approval carries over
  (a new Run always starts with empty consent rows);
- advances ``agent_input_revision`` (and the /v1 ``revision`` token) so old
  Runs and pending change proposals can no longer be applied;
- does NOT create a Run: the host starts one through the normal API.

Preconditions are deliberately conservative (see the report): host only, the
room is a Potato Meet room, still open, the caller names the round it is
closing, and that round already has a final result.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db_v21.models.agent import AgentRun, CoordinationRound
from db_v21.models.room import Room
from services.agent_run import authorize_room_host
from services.meeting_domain import is_potato_meet, supersede_open_runs

SessionFactory = Callable[[], Session]
MAX_REASON_CHARS = 500


class RoundError(Exception):
    code = "COORDINATION_ROUND_ERROR"
    status_code = 409


class InvalidRoundRequestError(RoundError):
    code = "INVALID_ROUND_REQUEST"
    status_code = 422


class NotPotatoMeetError(RoundError):
    code = "NOT_A_POTATO_MEET_ROOM"


class RoomNotOpenError(RoundError):
    code = "ROOM_NOT_OPEN"


class RoundConflictError(RoundError):
    code = "COORDINATION_ROUND_CONFLICT"


class RoundNotFinalizedError(RoundError):
    code = "ROUND_NOT_FINALIZED"


class RoundKeyReusedError(RoundError):
    code = "IDEMPOTENCY_KEY_REUSED"


@dataclass(frozen=True)
class RoundOpening:
    id: str
    room_id: str
    from_round: int
    to_round: int
    opened_input_revision: int
    closed_run_id: str | None
    reason: str | None
    created_at: datetime
    changed: bool


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _opening(row: CoordinationRound, *, changed: bool) -> RoundOpening:
    return RoundOpening(
        id=row.id,
        room_id=row.room_id,
        from_round=row.from_round,
        to_round=row.to_round,
        opened_input_revision=row.opened_input_revision,
        closed_run_id=row.closed_run_id,
        reason=row.reason,
        created_at=row.created_at,
        changed=changed,
    )


def open_next_coordination_round(
    session_factory: SessionFactory,
    *,
    room_id: str,
    actor_account_id: str,
    idempotency_key: str,
    expected_round: int,
    reason: str | None = None,
) -> RoundOpening:
    if (
        not isinstance(idempotency_key, str)
        or not idempotency_key.strip()
        or len(idempotency_key) > 200
        or not isinstance(expected_round, int)
        or isinstance(expected_round, bool)
        or expected_round < 0
        or (reason is not None and len(reason) > MAX_REASON_CHARS)
    ):
        raise InvalidRoundRequestError("Invalid round request.")
    key_hash = _hash(idempotency_key)
    clean_reason = (reason or "").strip() or None
    request_hash = _hash(f"{expected_round}|{clean_reason or ''}")
    try:
        return _open(
            session_factory, room_id, actor_account_id, key_hash, request_hash,
            expected_round, clean_reason,
        )
    except IntegrityError:  # a concurrent identical request committed first
        with session_factory() as db:
            existing = db.scalar(
                select(CoordinationRound).where(
                    CoordinationRound.room_id == room_id,
                    CoordinationRound.idempotency_key_hash == key_hash,
                )
            )
            if existing is None or existing.request_hash != request_hash:
                raise RoundConflictError("The round changed concurrently.") from None
            return _opening(existing, changed=False)


def _open(
    session_factory, room_id, actor_account_id, key_hash, request_hash,
    expected_round, reason,
) -> RoundOpening:
    with session_factory() as db:
        with db.begin():
            room = db.scalar(
                select(Room)
                .where(Room.id == room_id, Room.deleted_at.is_(None))
                .with_for_update()
            )
            actor = authorize_room_host(db, room_id=room_id, actor_account_id=actor_account_id)
            existing = db.scalar(
                select(CoordinationRound).where(
                    CoordinationRound.room_id == room_id,
                    CoordinationRound.idempotency_key_hash == key_hash,
                )
            )
            if existing is not None:  # replay: no second transition
                if existing.request_hash != request_hash:
                    raise RoundKeyReusedError("Idempotency-Key was used with a different request.")
                return _opening(existing, changed=False)
            if not is_potato_meet(room):
                raise NotPotatoMeetError("Only Potato Meet rooms have coordination rounds.")
            # A closed admin cycle is read-only. Opening a round there would STALE the
            # open Runs and bump the revision while every later write still fails,
            # so refuse before changing anything (a no-op unless ADMIN_ENABLED=1).
            from admin import lifecycle

            lifecycle.check(db, room, write=True)
            if room.progress_status in ("finalized", "cancelled", "deleted"):
                raise RoomNotOpenError("The room no longer accepts a new round.")
            if room.coordination_round != expected_round:
                raise RoundConflictError("The room is not in the round you expected.")
            final = db.scalar(
                select(AgentRun).where(
                    AgentRun.room_id == room.id,
                    AgentRun.finalized_at.is_not(None),
                    AgentRun.finalized_room_round == room.coordination_round,
                )
            )
            if final is None:
                raise RoundNotFinalizedError(
                    "The current round has no final result; adjust it with a change proposal."
                )
            supersede_open_runs(db, room.id, "Superseded by a new coordination round.")
            room.coordination_round += 1
            room.agent_input_revision += 1
            room.revision += 1
            row = CoordinationRound(
                room_id=room.id,
                from_round=expected_round,
                to_round=expected_round + 1,
                opened_by_member_id=actor.room_member_id,
                idempotency_key_hash=key_hash,
                request_hash=request_hash,
                reason=reason,
                closed_run_id=final.id,
                opened_input_revision=room.agent_input_revision,
            )
            db.add(row)
            db.flush()
            return _opening(row, changed=True)
