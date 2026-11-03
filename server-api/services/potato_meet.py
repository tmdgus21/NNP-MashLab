"""Potato Meet entry flow: create room, join / invite / RSVP, own availability.

Reuses the v2.1 account sessions, ``rooms``, ``room_members``,
``room_invitations`` and ``condition_submissions`` tables; no new tables.

Domain notes
- A room is a Potato Meet room because ``meeting_settings.coordination`` exists;
  the server validates that block with the same parser the Agent snapshot uses.
- Participant IDs are account IDs (the Agent contract).
- Invitation state, RSVP and availability are three independent facts:
  ``invitationStatus`` (not_sent/sent), ``participationStatus``
  (pending/accepted/declined) and ``availability.status``
  (not_submitted/submitted). Nothing here turns a missing answer or a missing
  submission into an absence.
- Every change to Agent input goes through ``record_input_change``: both
  revision counters advance and open Runs become STALE in the same transaction.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import date, datetime, time, timedelta
from typing import Annotated, Any, Callable, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.account import Account
from db_v21.models.agent import RoomInvitation
from db_v21.models.condition import ConditionAvailableSlot, ConditionSubmission
from db_v21.models.room import Room, RoomMember
from models import room_time_bounds
from services.agent_change import _assert_open_for_changes
from services.agent_run import (
    _claim_idempotency_record,
    _digest_key,
    authorize_room_host,
    authorize_room_member,
)
from services.meeting_domain import is_potato_meet, record_input_change
from services.meeting_snapshot import SnapshotConfigurationError, _parse_coordination_settings, _slot_minutes

SessionFactory = Callable[[], Session]
SEOUL = ZoneInfo("Asia/Seoul")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # same as /v1 join codes
MAX_ACTIVE_MEMBERS = 20  # same cap as /v1
MAX_SLOTS = 200
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _today() -> date:
    return datetime.now(SEOUL).date()


# ------------------------------------------------------------------ errors

class PotatoError(Exception):
    code = "POTATO_MEET_ERROR"
    status_code = 409


class InvalidPotatoRequestError(PotatoError):
    code = "INVALID_REQUEST"
    status_code = 422


class NotPotatoMeetRoomError(PotatoError):
    code = "NOT_A_POTATO_MEET_ROOM"


class RoomCodeNotFoundError(PotatoError):
    code = "ROOM_CODE_NOT_FOUND"
    status_code = 404


class InvitationNotFoundError(PotatoError):
    code = "INVITATION_NOT_FOUND"
    status_code = 404


class IdempotencyKeyReusedError(PotatoError):
    code = "IDEMPOTENCY_KEY_REUSED"


class RoomFullError(PotatoError):
    code = "ROOM_FULL"


class NicknameTakenError(PotatoError):
    code = "NICKNAME_TAKEN"


class MembershipInactiveError(PotatoError):
    code = "MEMBERSHIP_INACTIVE"


class InvitationExcludedError(PotatoError):
    code = "INVITATION_EXCLUDED"
    status_code = 403


class InvitationNotSentError(PotatoError):
    code = "INVITATION_NOT_SENT"


class AlreadyAnsweredError(PotatoError):
    code = "INVITATION_ALREADY_ANSWERED"


class AlreadyAcceptedError(PotatoError):
    code = "INVITATION_ALREADY_ACCEPTED"


class UnknownAccountError(PotatoError):
    code = "UNKNOWN_ACCOUNT"
    status_code = 422


class EmptyAvailabilityError(InvalidPotatoRequestError):
    """Empty lists are invalid by DOMAIN_POLICY; the client explains what to do instead."""

    code = "AVAILABILITY_EMPTY"


class ExclusionDisabledError(PotatoError):
    code = "RSVP_DEADLINE_REQUIRED"


class HostCannotLeaveError(PotatoError):
    code = "HOST_CANNOT_LEAVE"


class LeaveNotSupportedError(PotatoError):
    code = "LEAVE_NOT_SUPPORTED_FOR_INVITED"


class MinimumExceedsEligibleError(PotatoError):
    code = "MINIMUM_EXCEEDS_ELIGIBLE"
    status_code = 422


class VersionConflictError(PotatoError):
    code = "SUBMISSION_VERSION_CONFLICT"


class InputRevisionConflictError(PotatoError):
    code = "INPUT_REVISION_CONFLICT"


# ---------------------------------------------------------------- requests

class CreateRoomRequest(BaseModel):
    """Step 1 + Step 3 settings. durationMinutes is already parsed by the client
    ("2시간" -> 120); candidate dates are explicit, not inferred from slots."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    activity: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    duration_minutes: Annotated[StrictInt, Field(ge=1, le=1440)] = Field(alias="durationMinutes")
    dates: Annotated[list[date], Field(min_length=1, max_length=31)]
    minimum_attendee_count: Annotated[StrictInt, Field(ge=2, le=MAX_ACTIVE_MEMBERS)] = Field(
        default=2, alias="minimumAttendeeCount"
    )
    time_zone: Literal["Asia/Seoul"] = Field(default="Asia/Seoul", alias="timeZone")
    nickname: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class SlotIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str | None = None  # client-side key, ignored
    date: date
    start_time_minutes: StrictInt = Field(alias="startTimeMinutes")
    end_time_minutes: StrictInt = Field(alias="endTimeMinutes")


class SubmitAvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    time_zone: Literal["Asia/Seoul"] = Field(default="Asia/Seoul", alias="timeZone")
    time_slots: Annotated[list[SlotIn], Field(max_length=MAX_SLOTS)] = Field(alias="timeSlots")
    expected_version: StrictInt | None = Field(default=None, ge=0, alias="expectedVersion")


# ------------------------------------------------------------------ helpers

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ungated_exclusion_enabled() -> bool:
    """Development/test switch only. Releases leave it unset, which disables host exclusion."""
    return os.getenv("POTATO_ALLOW_UNGATED_EXCLUSION") == "1"


def _lifecycle_check(db: Session, room: Room, *, write: bool) -> None:
    from admin import lifecycle  # no-op unless ADMIN_ENABLED=1

    lifecycle.check(db, room, write=write)


def _lock_room(db: Session, room_id: str) -> Room:
    room = db.scalar(
        select(Room).where(Room.id == room_id, Room.deleted_at.is_(None)).with_for_update()
    )
    if room is None:
        raise RoomCodeNotFoundError("The room does not exist.")
    if not is_potato_meet(room):
        raise NotPotatoMeetRoomError("This is not a Potato Meet room.")
    return room


def _active_members(db: Session, room_id: str) -> list[RoomMember]:
    return list(
        db.scalars(
            select(RoomMember)
            .where(RoomMember.room_id == room_id, RoomMember.membership_status == "ACTIVE")
            .order_by(RoomMember.id)
        )
    )


def _coordination(room: Room) -> dict[str, Any]:
    return room.meeting_settings["coordination"]


def _active_dates(room: Room) -> set[date]:
    settings = _parse_coordination_settings(room.meeting_settings)
    return set(settings.dates) - set(settings.excluded_dates)


def _slots_to_minutes(rows) -> list[tuple[date, int, int]]:
    merged: dict[date, list[list[int]]] = {}
    for row in sorted(rows, key=lambda item: item.starts_at):
        day, start, end = _slot_minutes(row.starts_at, row.ends_at)
        merged.setdefault(day, []).append([start, end])
    return _merge({day: [tuple(pair) for pair in pairs] for day, pairs in merged.items()})


def _merge(by_day: dict[date, list[tuple[int, int]]]) -> list[tuple[date, int, int]]:
    """Same rule as the Kotlin mergeTimeSlots: overlapping OR touching ranges join."""
    result: list[tuple[date, int, int]] = []
    for day in sorted(by_day):
        current: list[int] | None = None
        for start, end in sorted(by_day[day]):
            if current is not None and current[1] >= start:
                current[1] = max(current[1], end)
            else:
                if current is not None:
                    result.append((day, current[0], current[1]))
                current = [start, end]
        if current is not None:
            result.append((day, current[0], current[1]))
    return result


def normalize_slots(
    slots: list[SlotIn], *, active_dates: set[date], today: date
) -> list[tuple[date, int, int]]:
    by_day: dict[date, list[tuple[int, int]]] = {}
    for slot in slots:
        if slot.date not in active_dates:
            raise InvalidPotatoRequestError(f"{slot.date.isoformat()} is not an active meeting date.")
        if slot.date < today:
            raise InvalidPotatoRequestError("Past dates cannot be submitted.")
        if not (0 <= slot.start_time_minutes < slot.end_time_minutes <= 1440):
            raise InvalidPotatoRequestError("A time range must satisfy 0 <= start < end <= 1440.")
        by_day.setdefault(slot.date, []).append((slot.start_time_minutes, slot.end_time_minutes))
    return _merge(by_day)


def _slot_json(slots: list[tuple[date, int, int]]) -> list[dict[str, Any]]:
    return [{"date": d.isoformat(), "startTimeMinutes": s, "endTimeMinutes": e} for d, s, e in slots]


def _latest_submission(db: Session, member_id: str) -> ConditionSubmission | None:
    return db.scalar(
        select(ConditionSubmission)
        .where(ConditionSubmission.room_member_id == member_id)
        .order_by(ConditionSubmission.version.desc())
        .limit(1)
    )


def _submission_slots(db: Session, submission: ConditionSubmission) -> list[tuple[date, int, int]]:
    rows = list(
        db.scalars(
            select(ConditionAvailableSlot).where(
                ConditionAvailableSlot.condition_submission_id == submission.id
            )
        )
    )
    return _slots_to_minutes(rows)


# ------------------------------------------------------------------- views

def _room_view(db: Session, room: Room, viewer_account_id: str | None, *, replayed: bool = False) -> dict[str, Any]:
    settings = _coordination(room)
    members = _active_members(db, room.id)
    me = next((m for m in members if m.account_id == viewer_account_id), None)
    return {
        "roomId": room.id,
        "code": room.code,
        "title": room.title,
        "activity": settings["activity"],
        "location": settings["location"],
        "durationMinutes": settings["durationMinutes"],
        "dates": settings["dates"],
        "excludedDates": settings.get("excludedDates", []),
        "minimumAttendeeCount": settings["minimumAttendeeCount"],
        "timeZone": settings["timeZone"],
        "hostMemberId": room.host_member_id,
        "status": room.progress_status,
        "coordinationRound": room.coordination_round,
        "agentInputRevision": room.agent_input_revision,
        "eligibleParticipantCount": len(members),
        "me": None if me is None else {
            "memberId": me.id,
            "accountId": me.account_id,
            "role": "organizer" if me.id == room.host_member_id else "invitee",
        },
        "replayed": replayed,
    }


# ----------------------------------------------------------------- create

def create_room(
    session_factory: SessionFactory,
    *,
    account_id: str,
    idempotency_key: str,
    request: CreateRoomRequest,
    today: date | None = None,
) -> dict[str, Any]:
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 200:
        raise InvalidPotatoRequestError("Idempotency-Key must be 1 to 200 characters.")
    today = today or _today()
    dates = sorted(set(request.dates))
    if len(dates) != len(request.dates):
        raise InvalidPotatoRequestError("Meeting dates must be unique.")
    if dates[0] < today:
        raise InvalidPotatoRequestError("Past meeting dates are not allowed.")
    coordination = {
        "schemaVersion": 1,
        "activity": request.activity,
        "location": request.location,
        "durationMinutes": request.duration_minutes,
        "dates": [d.isoformat() for d in dates],
        "excludedDates": [],
        "timeZone": "Asia/Seoul",
        "minimumAttendeeCount": request.minimum_attendee_count,
        "requiredStartMinutesByDate": {},
        "absoluteTimeWindows": [],
    }
    try:  # the server, not the client, owns validity of the coordination block
        _parse_coordination_settings({"coordination": coordination})
    except SnapshotConfigurationError as exc:
        raise InvalidPotatoRequestError(str(exc)) from exc

    payload = request.model_dump(mode="json", by_alias=True)
    request_hash = _hash(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    scope = f"potato-room:{_hash(account_id)[:50]}"
    with session_factory() as db:
        with db.begin():
            record, created = _claim_idempotency_record(
                db, scope=scope, key_hash=_digest_key(idempotency_key), request_hash=request_hash
            )
            if not created:
                if record.request_hash != request_hash:
                    raise IdempotencyKeyReusedError("Idempotency-Key was used with a different request.")
                room = db.get(Room, record.resource_id) if record.resource_id else None
                if room is None:
                    raise IdempotencyKeyReusedError("The earlier request did not complete.")
                return _room_view(db, room, account_id, replayed=True)

            for _ in range(20):
                code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
                if not db.scalar(select(Room.id).where(Room.code == code)):
                    break
            else:  # pragma: no cover
                raise PotatoError("Could not allocate an invite code.")
            starts_at, ends_at = room_time_bounds({"dates": coordination["dates"]})
            room = Room(
                code=code,
                created_by_account_id=account_id,
                title=request.title,
                starts_at=starts_at,
                ends_at=ends_at,
                lifecycle_status="COLLECTING_CONDITIONS",
                progress_status="collecting",
                meeting_settings={"coordination": coordination},
                dirty=True,
                current_round=0,
                coordination_round=0,
                revision=1,
                agent_input_revision=1,
            )
            db.add(room)
            db.flush()
            host = RoomMember(
                room_id=room.id, account_id=account_id, nickname=request.nickname,
                room_role="OWNER", membership_status="ACTIVE",
            )
            db.add(host)
            db.flush()
            room.host_member_id = host.id
            record.resource_type, record.resource_id = "potato_room", room.id
            from admin.security import enabled  # mirrors /v1 creation

            if enabled():
                from admin import lifecycle

                lifecycle.ensure(db, room)
            return _room_view(db, room, account_id)


# -------------------------------------------------------------- read paths

def get_room(session_factory: SessionFactory, *, room_id: str, account_id: str) -> dict[str, Any]:
    with session_factory() as db:
        authorize_room_member(db, room_id=room_id, actor_account_id=account_id)
        room = db.scalar(select(Room).where(Room.id == room_id, Room.deleted_at.is_(None)))
        if not is_potato_meet(room):
            raise NotPotatoMeetRoomError("This is not a Potato Meet room.")
        _lifecycle_check(db, room, write=False)
        return _room_view(db, room, account_id)


def list_participants(session_factory: SessionFactory, *, room_id: str, account_id: str) -> dict[str, Any]:
    with session_factory() as db:
        authorize_room_member(db, room_id=room_id, actor_account_id=account_id)
        room = db.scalar(select(Room).where(Room.id == room_id, Room.deleted_at.is_(None)))
        if not is_potato_meet(room):
            raise NotPotatoMeetRoomError("This is not a Potato Meet room.")
        members = _active_members(db, room.id)
        member_by_account = {m.account_id: m for m in members}
        invitations = {
            i.account_id: i
            for i in db.scalars(select(RoomInvitation).where(RoomInvitation.room_id == room.id))
        }
        rows: list[dict[str, Any]] = []
        for account, member in sorted(member_by_account.items()):
            if member.id == room.host_member_id:
                role, inv, part, elig = "organizer", "not_applicable", "accepted", "active"
                join_path = "organizer"
            else:
                invitation = invitations.get(account)
                # A member with no invitation row joined with the room code. (A row
                # that the join accepted is indistinguishable from an answered invite.)
                join_path = "invitation" if invitation else "code"
                role = "invitee"
                inv = "sent" if invitation and invitation.invitation_status == "SENT" else "not_sent"
                part, elig = "accepted", "active"
            latest = _latest_submission(db, member.id)
            rows.append({
                "participantId": account, "memberId": member.id, "displayName": member.nickname,
                "role": role, "invitationStatus": inv, "participationStatus": part,
                "eligibility": elig, "joinPath": join_path,
                "availability": {
                    "status": "submitted" if latest else "not_submitted",
                    "version": latest.version if latest else 0,
                    "updatedAt": latest.submitted_at.isoformat() if latest else None,
                },
            })
        for account, invitation in sorted(invitations.items()):
            if account in member_by_account:
                continue
            rows.append({
                "participantId": account, "memberId": None, "displayName": None,
                "role": "invitee", "joinPath": "invitation",
                "invitationStatus": "sent" if invitation.invitation_status == "SENT" else "not_sent",
                "participationStatus": invitation.response_status.lower(),
                "eligibility": "active" if invitation.eligibility_status == "ACTIVE" else "excluded_by_host",
                "availability": {"status": "not_submitted", "version": 0, "updatedAt": None},
            })
        return {"roomId": room.id, "participants": rows, "eligibleParticipantCount": len(members)}


def list_my_invitations(session_factory: SessionFactory, *, account_id: str) -> dict[str, Any]:
    with session_factory() as db:
        rows = []
        for invitation, room in db.execute(
            select(RoomInvitation, Room)
            .join(Room, Room.id == RoomInvitation.room_id)
            .where(
                RoomInvitation.account_id == account_id,
                RoomInvitation.invitation_status == "SENT",
                Room.deleted_at.is_(None),
            )
            .order_by(RoomInvitation.invited_at.desc())
        ):
            if not is_potato_meet(room):
                continue
            rows.append({
                "roomId": room.id, "title": room.title,
                "participationStatus": invitation.response_status.lower(),
                "eligibility": "active" if invitation.eligibility_status == "ACTIVE" else "excluded_by_host",
                "invitedAt": invitation.invited_at.isoformat() if invitation.invited_at else None,
            })
        return {"invitations": rows}


def list_recent_people(
    session_factory: SessionFactory,
    *,
    account_id: str,
    query: str | None = None,
    for_room_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Invite candidates derived from rooms the caller already belongs to.

    This is not a friend list and not a user directory: it only shows people
    the caller has already seen (nickname + account ID) in a shared Potato Meet
    room, so no new information is exposed and no account can be enumerated.
    With ``for_room_id`` each person is annotated with their state in that room.
    """
    if not 1 <= limit <= 100:
        raise InvalidPotatoRequestError("limit must be between 1 and 100.")
    needle = (query or "").strip().casefold()
    with session_factory() as db:
        room_state: dict[str, str] = {}
        if for_room_id is not None:
            authorize_room_member(db, room_id=for_room_id, actor_account_id=account_id)
            for member in _active_members(db, for_room_id):
                room_state[member.account_id] = "member"
            for invitation in db.scalars(select(RoomInvitation).where(RoomInvitation.room_id == for_room_id)):
                if invitation.account_id in room_state:
                    continue
                room_state[invitation.account_id] = (
                    "excluded" if invitation.eligibility_status != "ACTIVE"
                    else invitation.response_status.lower() if invitation.invitation_status == "SENT"
                    else "not_sent"
                )
        my_rooms = select(RoomMember.room_id).where(
            RoomMember.account_id == account_id, RoomMember.membership_status == "ACTIVE"
        )
        people: dict[str, dict[str, Any]] = {}
        rows = db.execute(
            select(RoomMember, Room)
            .join(Room, Room.id == RoomMember.room_id)
            .join(Account, Account.id == RoomMember.account_id)
            .where(
                RoomMember.room_id.in_(my_rooms),
                RoomMember.account_id != account_id,
                RoomMember.membership_status == "ACTIVE",
                Room.deleted_at.is_(None),
                Account.account_type == "USER",
                Account.account_status == "ACTIVE",
                Account.approved.is_(True),
            )
            .order_by(RoomMember.joined_at.desc(), RoomMember.id)
        )
        for member, room in rows:
            if not is_potato_meet(room):
                continue
            entry = people.get(member.account_id)
            if entry is None:
                people[member.account_id] = entry = {
                    "accountId": member.account_id, "nickname": member.nickname,
                    "sharedRoomCount": 0, "lastSharedAt": member.joined_at.isoformat(),
                    "_names": set(), "inRoom": room_state.get(member.account_id) if for_room_id else None,
                }
            entry["sharedRoomCount"] += 1
            entry["_names"].add(member.nickname.casefold())
        result = []
        for entry in people.values():
            names = entry.pop("_names")
            if needle and not any(needle in name for name in names):
                continue
            result.append(entry)
        return {"people": result[:limit]}


# -------------------------------------------------------- join / invite / RSVP

def join_room(
    session_factory: SessionFactory,
    *,
    account_id: str,
    code: str,
    nickname: str,
) -> dict[str, Any]:
    """Link/code join: joining is acceptance. An existing invitation (if any) is accepted."""
    nickname = (nickname or "").strip()
    if not 1 <= len(nickname) <= 30 or not code:
        raise InvalidPotatoRequestError("A room code and a 1-30 character nickname are required.")
    with session_factory() as db:
        with db.begin():
            room_id = db.scalar(
                select(Room.id).where(Room.code == code.strip().upper(), Room.deleted_at.is_(None))
            )
            if room_id is None:
                raise RoomCodeNotFoundError("Check the invite code.")
            room = _lock_room(db, room_id)
            existing = db.scalar(
                select(RoomMember).where(RoomMember.room_id == room.id, RoomMember.account_id == account_id)
            )
            if existing is not None:
                if existing.membership_status != "ACTIVE":
                    raise MembershipInactiveError("Your membership in this room is not active.")
                return _room_view(db, room, account_id, replayed=True)
            _assert_open_for_changes(db, room)
            _lifecycle_check(db, room, write=True)
            invitation = db.scalar(
                select(RoomInvitation).where(
                    RoomInvitation.room_id == room.id, RoomInvitation.account_id == account_id
                )
            )
            if invitation is not None and invitation.eligibility_status != "ACTIVE":
                raise InvitationExcludedError("The host excluded this invitation.")
            _accept(db, room, account_id, nickname, invitation)
            return _room_view(db, room, account_id)


def _accept(db: Session, room: Room, account_id: str, nickname: str, invitation: RoomInvitation | None) -> None:
    if len(_active_members(db, room.id)) >= MAX_ACTIVE_MEMBERS:
        raise RoomFullError("The room is full.")
    if db.scalar(select(RoomMember.id).where(RoomMember.room_id == room.id, RoomMember.nickname == nickname)):
        raise NicknameTakenError("That nickname is already used in this room.")
    db.add(RoomMember(
        room_id=room.id, account_id=account_id, nickname=nickname,
        room_role="MEMBER", membership_status="ACTIVE",
    ))
    if invitation is not None:
        stamp = now()
        if invitation.invitation_status != "SENT":
            invitation.invitation_status, invitation.invited_at = "SENT", stamp
        invitation.response_status, invitation.responded_at = "ACCEPTED", stamp
    db.flush()
    record_input_change(db, room, "A participant joined the room.")


def invite_accounts(
    session_factory: SessionFactory,
    *,
    room_id: str,
    actor_account_id: str,
    account_ids: list[str],
    send: bool = True,
) -> dict[str, Any]:
    """Host only. Creates (or sends) invitations for existing accounts. A recorded
    "sent" is a state, not a delivery: there is no push channel in the server."""
    ids = list(dict.fromkeys(account_ids))
    if not ids or len(ids) > MAX_ACTIVE_MEMBERS:
        raise InvalidPotatoRequestError(f"Invite 1 to {MAX_ACTIVE_MEMBERS} accounts at a time.")
    with session_factory() as db:
        with db.begin():
            room = _lock_room(db, room_id)
            actor = authorize_room_host(db, room_id=room_id, actor_account_id=actor_account_id)
            _assert_open_for_changes(db, room)
            _lifecycle_check(db, room, write=True)
            valid = set(db.scalars(select(Account.id).where(
                Account.id.in_(ids), Account.account_type == "USER",
                Account.account_status == "ACTIVE", Account.approved.is_(True),
            )))
            if valid != set(ids):
                raise UnknownAccountError("Every invited account must be an active user account.")
            members = {m.account_id for m in _active_members(db, room.id)}
            results, changed = [], False
            for account_id in ids:
                invitation = db.scalar(select(RoomInvitation).where(
                    RoomInvitation.room_id == room.id, RoomInvitation.account_id == account_id))
                if account_id in members:
                    result = "already_member"
                elif invitation is None:
                    stamp = now()
                    db.add(RoomInvitation(
                        room_id=room.id, account_id=account_id, invited_by_member_id=actor.room_member_id,
                        invitation_status="SENT" if send else "NOT_SENT",
                        invited_at=stamp if send else None,
                    ))
                    result, changed = ("sent" if send else "created"), True
                elif invitation.eligibility_status != "ACTIVE":
                    result = "excluded"
                elif send and invitation.invitation_status == "NOT_SENT":
                    invitation.invitation_status, invitation.invited_at = "SENT", now()
                    result, changed = "sent", True
                else:
                    result = "unchanged"
                results.append({"accountId": account_id, "result": result})
            db.flush()
            if changed:
                record_input_change(db, room, "Invitations changed.")
            return {"roomId": room.id, "results": results, "agentInputRevision": room.agent_input_revision}


def respond_to_invitation(
    session_factory: SessionFactory,
    *,
    room_id: str,
    account_id: str,
    response: Literal["ACCEPTED", "DECLINED"],
    nickname: str | None = None,
) -> dict[str, Any]:
    if response not in ("ACCEPTED", "DECLINED"):
        raise InvalidPotatoRequestError("response must be ACCEPTED or DECLINED.")
    with session_factory() as db:
        with db.begin():
            room = _lock_room(db, room_id)
            invitation = db.scalar(select(RoomInvitation).where(
                RoomInvitation.room_id == room.id, RoomInvitation.account_id == account_id))
            if invitation is None:
                raise InvitationNotFoundError("There is no invitation for this account.")
            if invitation.invitation_status != "SENT":
                raise InvitationNotSentError("The invitation has not been sent yet.")
            if invitation.eligibility_status != "ACTIVE":
                raise InvitationExcludedError("The host excluded this invitation.")
            if invitation.response_status == response:  # idempotent replay
                return _room_view(db, room, account_id, replayed=True)
            if invitation.response_status == "ACCEPTED":
                raise AlreadyAcceptedError("An accepted invitation cannot be declined here.")
            _assert_open_for_changes(db, room)
            _lifecycle_check(db, room, write=True)
            if response == "ACCEPTED":
                name = (nickname or "").strip()
                if not 1 <= len(name) <= 30:
                    raise InvalidPotatoRequestError("A 1-30 character nickname is required to accept.")
                existing = db.scalar(select(RoomMember).where(
                    RoomMember.room_id == room.id, RoomMember.account_id == account_id))
                if existing is not None:
                    raise MembershipInactiveError("Your membership in this room is not active.")
                _accept(db, room, account_id, name, invitation)
            else:
                invitation.response_status, invitation.responded_at = "DECLINED", now()
                db.flush()
                record_input_change(db, room, "An invitation was declined.")
            return _room_view(db, room, account_id)


def exclude_pending_invitee(
    session_factory: SessionFactory,
    *,
    room_id: str,
    actor_account_id: str,
    account_id: str,
    reason: str,
) -> dict[str, Any]:
    """Host only, explicit. Without it one unanswered invitee would hold the Agent
    in WAITING_FOR_INPUT forever. Only a still-pending SENT invitation can be
    excluded (the table's own rule); nothing is ever excluded automatically."""
    if not _ungated_exclusion_enabled():
        # DOMAIN_POLICY allows exclusion only AFTER the RSVP deadline, but the
        # deadline (rsvpDeadlineAt) does not exist yet, so the check cannot be made.
        raise ExclusionDisabledError(
            "Excluding an invitee requires an RSVP deadline, which is not supported yet."
        )
    reason = (reason or "").strip()
    if not 1 <= len(reason) <= 200:
        raise InvalidPotatoRequestError("A 1-200 character reason is required.")
    with session_factory() as db:
        with db.begin():
            room = _lock_room(db, room_id)
            actor = authorize_room_host(db, room_id=room_id, actor_account_id=actor_account_id)
            invitation = db.scalar(select(RoomInvitation).where(
                RoomInvitation.room_id == room.id, RoomInvitation.account_id == account_id))
            if invitation is None:
                raise InvitationNotFoundError("There is no invitation for this account.")
            if invitation.eligibility_status == "EXCLUDED_BY_HOST":
                return _room_view(db, room, actor_account_id, replayed=True)
            if invitation.invitation_status != "SENT" or invitation.response_status != "PENDING":
                raise AlreadyAnsweredError("Only a sent, unanswered invitation can be excluded.")
            _assert_open_for_changes(db, room)
            _lifecycle_check(db, room, write=True)
            invitation.eligibility_status = "EXCLUDED_BY_HOST"
            invitation.excluded_at = now()
            invitation.excluded_by_member_id = actor.room_member_id
            invitation.exclusion_reason = reason
            from admin.security import log  # DOMAIN_POLICY: reasoned, authenticated, audited

            log(db, "request", "room.exclude_invitee", room.id,
                reason=f"actor={actor_account_id} invitee={account_id} reason={reason}")
            db.flush()
            record_input_change(db, room, "An unanswered invitee was excluded by the host.")
            return _room_view(db, room, actor_account_id)


def leave_room(session_factory: SessionFactory, *, room_id: str, account_id: str) -> dict[str, Any]:
    """Explicit, user-initiated leave. Soft (membership LEFT): submissions and every
    candidate/consent row stay as history. Only members WITHOUT an invitation row
    (code joiners) can leave: the snapshot builder rejects an invitation account
    whose membership is inactive, so leaving an invitation would break every Run."""
    with session_factory() as db:
        with db.begin():
            room = _lock_room(db, room_id)
            member = db.scalar(select(RoomMember).where(
                RoomMember.room_id == room.id, RoomMember.account_id == account_id))
            if member is None:
                raise InvitationNotFoundError("You are not a member of this room.")
            if member.membership_status == "LEFT":
                return {"roomId": room.id, "left": True, "replayed": True,
                        "agentInputRevision": room.agent_input_revision}
            if member.membership_status != "ACTIVE":
                raise MembershipInactiveError("Your membership in this room is not active.")
            if member.id == room.host_member_id:
                raise HostCannotLeaveError("The host cannot leave the room.")
            if db.scalar(select(RoomInvitation.id).where(
                    RoomInvitation.room_id == room.id, RoomInvitation.account_id == account_id)):
                raise LeaveNotSupportedError("An invited member cannot leave in this version.")
            _assert_open_for_changes(db, room)
            _lifecycle_check(db, room, write=True)
            member.membership_status = "LEFT"
            db.flush()
            record_input_change(db, room, "A participant left the room.")
            return {"roomId": room.id, "left": True, "replayed": False,
                    "agentInputRevision": room.agent_input_revision}


def latest_run(session_factory: SessionFactory, *, room_id: str, account_id: str) -> dict[str, Any]:
    """The newest Run of the room (any status) so every participant's phone follows the
    same Run. STALE means the input changed after it was computed: compute again."""
    from db_v21.models.agent import AgentRun

    with session_factory() as db:
        authorize_room_member(db, room_id=room_id, actor_account_id=account_id)
        room = db.scalar(select(Room).where(Room.id == room_id, Room.deleted_at.is_(None)))
        if not is_potato_meet(room):
            raise NotPotatoMeetError("This is not a Potato Meet room.")
        run = db.scalar(
            select(AgentRun).where(AgentRun.room_id == room_id)
            .order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(1)
        )
        if run is None:
            return {"roomId": room_id, "run": None, "currentInputRevision": room.agent_input_revision}
        return {
            "roomId": room_id,
            "currentInputRevision": room.agent_input_revision,
            "run": {
                "runId": run.id, "status": run.status, "errorCode": run.error_code,
                "createdAt": run.created_at.isoformat(),
                "sourceRevision": run.source_revision,
                "current": run.source_revision == room.agent_input_revision and run.status != "STALE",
                "approvalStatus": run.approval_status,
                "selectedCandidateId": run.selected_candidate_id,
                "finalized": run.finalized_at is not None,
            },
        }


def list_my_rooms(session_factory: SessionFactory, *, account_id: str, limit: int = 50) -> dict[str, Any]:
    """Home screen: Potato Meet rooms the caller is an ACTIVE member of."""
    if not 1 <= limit <= 100:
        raise InvalidPotatoRequestError("limit must be between 1 and 100.")
    from db_v21.models.agent import AgentCandidate, AgentRun

    with session_factory() as db:
        rows = []
        for member, room in db.execute(
            select(RoomMember, Room)
            .join(Room, Room.id == RoomMember.room_id)
            .where(RoomMember.account_id == account_id, RoomMember.membership_status == "ACTIVE",
                   Room.deleted_at.is_(None))
            .order_by(Room.created_at.desc())
        ):
            if not is_potato_meet(room):
                continue
            settings = _coordination(room)
            final = db.scalar(select(AgentRun).where(
                AgentRun.room_id == room.id, AgentRun.finalized_at.is_not(None),
                AgentRun.finalized_room_round == room.coordination_round))
            candidate = db.get(AgentCandidate, final.selected_candidate_id) if final else None
            rows.append({
                "roomId": room.id, "code": room.code, "title": room.title,
                "activity": settings["activity"], "location": settings["location"],
                "durationMinutes": settings["durationMinutes"], "dates": settings["dates"],
                "role": "organizer" if member.id == room.host_member_id else "invitee",
                "myNickname": member.nickname,
                "eligibleParticipantCount": len(_active_members(db, room.id)),
                "coordinationRound": room.coordination_round,
                "finalized": final is not None,
                "finalStartsAt": candidate.starts_at.isoformat() if candidate else None,
                "finalEndsAt": candidate.ends_at.isoformat() if candidate else None,
            })
        return {"rooms": rows[:limit]}


# ------------------------------------------------------- minimum attendees

def set_minimum_attendees(
    session_factory: SessionFactory,
    *,
    room_id: str,
    actor_account_id: str,
    minimum: int,
    expected_input_revision: int | None = None,
) -> dict[str, Any]:
    """Host only. Keeps the Agent rule: at least 2, and not above the eligible count."""
    with session_factory() as db:
        with db.begin():
            room = _lock_room(db, room_id)
            authorize_room_host(db, room_id=room_id, actor_account_id=actor_account_id)
            if type(minimum) is not int or minimum < 2:
                raise InvalidPotatoRequestError("minimumAttendeeCount must be an integer of at least 2.")
            if _coordination(room)["minimumAttendeeCount"] == minimum:
                return _room_view(db, room, actor_account_id, replayed=True)
            if expected_input_revision is not None and expected_input_revision != room.agent_input_revision:
                raise InputRevisionConflictError("The room input changed; reload and retry.")
            _assert_open_for_changes(db, room)
            _lifecycle_check(db, room, write=True)
            eligible = len(_active_members(db, room.id))
            if minimum > eligible:
                raise MinimumExceedsEligibleError(
                    f"minimumAttendeeCount cannot exceed the {eligible} eligible participants."
                )
            settings = json.loads(json.dumps(room.meeting_settings))
            settings["coordination"]["minimumAttendeeCount"] = minimum
            room.meeting_settings = settings
            record_input_change(db, room, "The minimum attendee count changed.")
            return _room_view(db, room, actor_account_id)


# ------------------------------------------------------------ availability

def get_my_availability(session_factory: SessionFactory, *, room_id: str, account_id: str) -> dict[str, Any]:
    with session_factory() as db:
        actor = authorize_room_member(db, room_id=room_id, actor_account_id=account_id)
        latest = _latest_submission(db, actor.room_member_id)
        if latest is None:
            return {"participantId": account_id, "status": "not_submitted", "version": 0,
                    "timeZone": "Asia/Seoul", "timeSlots": [], "submittedAt": None}
        return {"participantId": account_id, "status": "submitted", "version": latest.version,
                "timeZone": "Asia/Seoul", "timeSlots": _slot_json(_submission_slots(db, latest)),
                "submittedAt": latest.submitted_at.isoformat()}


def submit_my_availability(
    session_factory: SessionFactory,
    *,
    room_id: str,
    account_id: str,
    request: SubmitAvailabilityRequest,
    today: date | None = None,
) -> dict[str, Any]:
    """Own availability only. Each change is a new version; an identical resubmit is a no-op."""
    today = today or _today()
    try:
        with session_factory() as db:
            with db.begin():
                room = _lock_room(db, room_id)
                actor = authorize_room_member(db, room_id=room_id, actor_account_id=account_id)
                slots = normalize_slots(request.time_slots, active_dates=_active_dates(room), today=today)
                if not slots:
                    # snapshots reject a submission without slots; an explicit
                    # "no availability" answer is not defined (open policy question)
                    raise EmptyAvailabilityError(
                        "At least one time slot is required. If you have no available time, "
                        "do not submit; tell the host or leave the room."
                    )
                latest = _latest_submission(db, actor.room_member_id)
                current = _submission_slots(db, latest) if latest else None
                if current == slots:
                    return _availability_result(latest, slots, room, changed=False)
                if request.expected_version is not None and request.expected_version != (latest.version if latest else 0):
                    raise VersionConflictError("Your availability changed elsewhere; reload and retry.")
                _assert_open_for_changes(db, room)
                _lifecycle_check(db, room, write=True)
                submission = ConditionSubmission(
                    room_member_id=actor.room_member_id,
                    version=(latest.version if latest else 0) + 1,
                    confirmed={"availability": [
                        {"date": d.isoformat(), "start": s, "end": e} for d, s, e in slots
                    ]},
                    ai_draft_id=None,
                    submitted_at=now(),
                )
                db.add(submission)
                db.flush()
                for day, start, end in slots:
                    midnight = datetime.combine(day, time.min, tzinfo=SEOUL)
                    db.add(ConditionAvailableSlot(
                        condition_submission_id=submission.id,
                        starts_at=midnight + timedelta(minutes=start),
                        ends_at=midnight + timedelta(minutes=end),
                    ))
                db.flush()
                record_input_change(db, room, "A participant's availability changed.")
                return _availability_result(submission, slots, room, changed=True)
    except IntegrityError as exc:  # two devices raced for the same next version
        raise VersionConflictError("Your availability changed elsewhere; reload and retry.") from exc


def _availability_result(submission, slots, room: Room, *, changed: bool) -> dict[str, Any]:
    return {
        "status": "submitted",
        "version": submission.version,
        "timeZone": "Asia/Seoul",
        "timeSlots": _slot_json(slots),
        "submittedAt": submission.submitted_at.isoformat(),
        "changed": changed,
        "agentInputRevision": room.agent_input_revision,
    }
