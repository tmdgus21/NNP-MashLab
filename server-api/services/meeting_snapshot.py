"""Build immutable Agent Core snapshots from v2.1 ORM records."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal, Sequence
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
    ValidationError,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

_AGENT_SOURCE = (
    Path(__file__).resolve().parents[2] / "experiments" / "potato-agent"
)
if (
    importlib.util.find_spec("potato_agent") is None
    and _AGENT_SOURCE.is_dir()
    and str(_AGENT_SOURCE) not in sys.path
):
    sys.path.insert(0, str(_AGENT_SOURCE))

from potato_agent.models import (  # noqa: E402
    AvailabilitySlot,
    AvailabilityStatus,
    AvailabilitySubmission,
    EligibilityStatus,
    InvitationStatus,
    MeetingSnapshot,
    Participant,
    ParticipantRole,
    ResponseStatus,
    AbsoluteTimeWindow,
)

from db_v21.models.agent import RoomInvitation  # noqa: E402
from db_v21.models.condition import (  # noqa: E402
    ConditionAvailableSlot,
    ConditionSubmission,
)
from db_v21.models.room import Room, RoomMember  # noqa: E402

SEOUL = ZoneInfo("Asia/Seoul")
NonEmptyText = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1)
]


class SnapshotBuildError(Exception):
    """Base error for invalid or unavailable snapshot input."""


class SnapshotConfigurationError(SnapshotBuildError):
    """The room's versioned Agent coordination settings are invalid."""

    def __init__(self, message: str, *, validation_errors: Sequence[dict] = ()):
        super().__init__(message)
        self.validation_errors = tuple(validation_errors)


class UnsupportedCoordinationVersionError(SnapshotConfigurationError):
    """The room uses an unsupported coordination settings version."""


class SnapshotDataError(SnapshotBuildError):
    """Stored v2.1 data cannot be represented by the Agent domain model."""


class RoomNotFoundError(SnapshotBuildError):
    """The requested room does not exist or is deleted."""


class InsufficientParticipantsError(SnapshotBuildError):
    """The room does not have enough eligible participants to create a snapshot."""


class _AbsoluteWindowSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    date: date
    start_minute: Annotated[StrictInt, Field(ge=0, le=1439)] = Field(
        alias="startMinute"
    )
    end_minute: Annotated[StrictInt, Field(ge=1, le=1440)] = Field(
        alias="endMinute"
    )

    @model_validator(mode="after")
    def validate_interval(self) -> _AbsoluteWindowSettings:
        if self.start_minute >= self.end_minute:
            raise ValueError("absolute time window must be a non-empty interval")
        return self


class _CoordinationSettings(BaseModel):
    """Version 1 of meeting_settings.coordination, using the Agent API casing."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(alias="schemaVersion")
    activity: NonEmptyText
    location: NonEmptyText
    duration_minutes: Annotated[StrictInt, Field(gt=0, le=1440)] = Field(
        alias="durationMinutes"
    )
    dates: tuple[date, ...]
    excluded_dates: tuple[date, ...] = Field(
        default=(), alias="excludedDates"
    )
    time_zone: Literal["Asia/Seoul"] = Field(alias="timeZone")
    minimum_attendee_count: Annotated[StrictInt, Field(ge=2)] = Field(
        alias="minimumAttendeeCount"
    )
    required_start_minutes_by_date: dict[
        date, Annotated[StrictInt, Field(ge=0, le=1439)]
    ] = Field(default_factory=dict, alias="requiredStartMinutesByDate")
    absolute_time_windows: tuple[_AbsoluteWindowSettings, ...] = Field(
        default=(), alias="absoluteTimeWindows"
    )

    @model_validator(mode="after")
    def validate_dates_and_constraints(self) -> _CoordinationSettings:
        if not self.dates:
            raise ValueError("at least one meeting date is required")
        if len(set(self.dates)) != len(self.dates):
            raise ValueError("meeting dates must be unique")
        if len(set(self.excluded_dates)) != len(self.excluded_dates):
            raise ValueError("excluded dates must be unique")
        allowed_dates = set(self.dates)
        if set(self.excluded_dates) - allowed_dates:
            raise ValueError("excluded dates must be configured meeting dates")
        if set(self.required_start_minutes_by_date) - allowed_dates:
            raise ValueError("required start times must use configured meeting dates")
        if any(
            minute + self.duration_minutes > 1440
            for minute in self.required_start_minutes_by_date.values()
        ):
            raise ValueError("required meeting time cannot extend beyond midnight")
        if any(window.date not in allowed_dates for window in self.absolute_time_windows):
            raise ValueError("absolute time windows must use configured meeting dates")
        return self


def _parse_coordination_settings(settings: object) -> _CoordinationSettings:
    if not isinstance(settings, dict):
        raise SnapshotConfigurationError("rooms.meeting_settings must be an object")
    coordination = settings.get("coordination")
    if not isinstance(coordination, dict):
        raise SnapshotConfigurationError(
            "rooms.meeting_settings.coordination is required"
        )
    version = coordination.get("schemaVersion")
    if type(version) is not int or version != 1:
        raise UnsupportedCoordinationVersionError(
            f"unsupported coordination schemaVersion: {version!r}"
        )
    try:
        return _CoordinationSettings.model_validate(coordination)
    except ValidationError as exc:
        raise SnapshotConfigurationError(
            "invalid rooms.meeting_settings.coordination",
            validation_errors=exc.errors(
                include_input=False, include_context=False
            ),
        ) from exc


def _to_seoul(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SEOUL)
    return dt.astimezone(SEOUL)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _slot_minutes(
    starts_at: datetime, ends_at: datetime
) -> tuple[date, int, int]:
    start = _to_seoul(starts_at)
    end = _to_seoul(ends_at)
    if start.second or start.microsecond or end.second or end.microsecond:
        raise SnapshotDataError("availability slots must use one-minute precision")
    start_minute = start.hour * 60 + start.minute
    if end.date() == start.date():
        end_minute = end.hour * 60 + end.minute
    elif end.date() == start.date() + timedelta(days=1) and end.time() == time.min:
        end_minute = 1440
    else:
        raise SnapshotDataError(
            "availability slots may not cross a Seoul calendar date boundary"
        )
    if start_minute >= end_minute:
        raise SnapshotDataError("availability slot must be a non-empty interval")
    return start.date(), start_minute, end_minute


def _normalize_slots(
    rows: Sequence[ConditionAvailableSlot], allowed_dates: set[date]
) -> tuple[AvailabilitySlot, ...]:
    grouped: dict[date, list[tuple[int, int]]] = defaultdict(list)
    for row in rows:
        slot_date, start_minute, end_minute = _slot_minutes(
            row.starts_at, row.ends_at
        )
        if slot_date not in allowed_dates:
            raise SnapshotDataError(
                f"availability slot date {slot_date.isoformat()} is not configured"
            )
        grouped[slot_date].append((start_minute, end_minute))

    normalized: list[AvailabilitySlot] = []
    for slot_date in sorted(grouped):
        merged: list[list[int]] = []
        for start_minute, end_minute in sorted(grouped[slot_date]):
            if merged and start_minute <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end_minute)
            else:
                merged.append([start_minute, end_minute])
        normalized.extend(
            AvailabilitySlot(
                date=slot_date,
                start_minute=start_minute,
                end_minute=end_minute,
                time_zone="Asia/Seoul",
            )
            for start_minute, end_minute in merged
        )
    return tuple(normalized)


def _canonical_hash_payload(
    *,
    room: Room,
    settings: _CoordinationSettings,
    participants: Sequence[Participant],
    availability: dict[str, AvailabilitySubmission],
) -> dict:
    return {
        "meeting_id": room.id,
        "coordination_schema_version": settings.schema_version,
        "input_revision": room.agent_input_revision,
        "title": room.title,
        "activity": settings.activity,
        "location": settings.location,
        "duration_minutes": settings.duration_minutes,
        "dates": [item.isoformat() for item in sorted(settings.dates)],
        "excluded_dates": [
            item.isoformat() for item in sorted(settings.excluded_dates)
        ],
        "time_zone": settings.time_zone,
        "minimum_attendee_count": settings.minimum_attendee_count,
        "required_start_minutes_by_date": {
            day.isoformat(): minute
            for day, minute in sorted(settings.required_start_minutes_by_date.items())
        },
        "absolute_time_windows": [
            window.model_dump(mode="json")
            for window in sorted(
                settings.absolute_time_windows,
                key=lambda item: (
                    item.date,
                    item.start_minute,
                    item.end_minute,
                ),
            )
        ],
        "participants": [
            participant.model_dump(mode="json")
            for participant in sorted(
                participants, key=lambda item: item.participant_id
            )
        ],
        "availability_by_participant_id": {
            participant_id: availability[participant_id].model_dump(mode="json")
            for participant_id in sorted(availability)
        },
    }


def build_meeting_snapshot(
    db: Session,
    *,
    room_id: str,
    agent_session_id: str,
    run_id: str,
    consent_round: int,
) -> MeetingSnapshot:
    """Read v2.1 state and return a detached, immutable Agent Core snapshot.

    The caller owns `db`; this function neither commits nor retains the session.
    Execution identifiers and consent round are deliberately excluded from the
    input hash, which represents meeting inputs rather than a particular run.
    """
    if not room_id or not agent_session_id or not run_id:
        raise SnapshotDataError("room, agent session, and run identifiers are required")
    if type(consent_round) is not int or consent_round < 1:
        raise SnapshotDataError("consent_round must be a positive integer")

    room = db.scalar(
        select(Room).where(Room.id == room_id, Room.deleted_at.is_(None))
    )
    if room is None:
        raise RoomNotFoundError(f"room {room_id!r} does not exist or is deleted")
    settings = _parse_coordination_settings(room.meeting_settings)

    members = list(
        db.scalars(
            select(RoomMember)
            .where(RoomMember.room_id == room.id)
            .order_by(RoomMember.id)
        )
    )
    active_members = {
        member.account_id: member
        for member in members
        if member.membership_status == "ACTIVE"
    }
    host = next(
        (member for member in members if member.id == room.host_member_id), None
    )
    owners = [
        member
        for member in members
        if member.membership_status == "ACTIVE" and member.room_role == "OWNER"
    ]
    if (
        host is None
        or host.membership_status != "ACTIVE"
        or host.room_role != "OWNER"
        or len(owners) != 1
    ):
        raise SnapshotDataError(
            "room host must be the only active OWNER member"
        )

    invitations = list(
        db.scalars(
            select(RoomInvitation)
            .where(RoomInvitation.room_id == room.id)
            .order_by(RoomInvitation.account_id)
        )
    )
    invitation_by_account: dict[str, RoomInvitation] = {}
    for invitation in invitations:
        if invitation.account_id == host.account_id:
            raise SnapshotDataError("the room host cannot also be an invitee")
        if invitation.invitation_status == "NOT_SENT":
            if (
                invitation.response_status != "PENDING"
                or invitation.eligibility_status != "ACTIVE"
            ):
                raise SnapshotDataError(
                    "an unsent invitation cannot have a response or exclusion"
                )
            continue
        if invitation.invited_by_member_id is not None and not any(
            member.id == invitation.invited_by_member_id for member in members
        ):
            raise SnapshotDataError(
                "invitation creator must be a member of the same room"
            )
        if invitation.response_status == "PENDING":
            if invitation.responded_at is not None:
                raise SnapshotDataError(
                    "pending invitation cannot have a response timestamp"
                )
        elif invitation.responded_at is None:
            raise SnapshotDataError(
                "answered invitation must have a response timestamp"
            )
        if (
            invitation.eligibility_status == "EXCLUDED_BY_HOST"
            and invitation.excluded_by_member_id != host.id
        ):
            raise SnapshotDataError(
                "explicit invitee exclusion must be recorded by the room host"
            )
        invitation_by_account[invitation.account_id] = invitation

    participant_by_account: dict[str, Participant] = {}
    for account_id, member in active_members.items():
        if member.id == host.id:
            participant_by_account[account_id] = Participant(
                participant_id=account_id,
                display_name=member.nickname,
                role=ParticipantRole.ORGANIZER,
                invitation_status=InvitationStatus.NOT_APPLICABLE,
                response_status=ResponseStatus.ACCEPTED,
                eligibility_status=EligibilityStatus.ACTIVE,
            )
            continue

        invitation = invitation_by_account.get(account_id)
        if invitation is None:
            participant_by_account[account_id] = Participant(
                participant_id=account_id,
                display_name=member.nickname,
                role=ParticipantRole.INVITEE,
                invitation_status=InvitationStatus.NOT_SENT,
                response_status=ResponseStatus.ACCEPTED,
                eligibility_status=EligibilityStatus.ACTIVE,
            )
            continue
        if (
            invitation.response_status != "ACCEPTED"
            or invitation.eligibility_status != "ACTIVE"
        ):
            raise SnapshotDataError(
                "an active room member must have an accepted, eligible invitation"
            )
        participant_by_account[account_id] = Participant(
            participant_id=account_id,
            display_name=member.nickname,
            role=ParticipantRole.INVITEE,
            invitation_status=InvitationStatus.SENT,
            response_status=ResponseStatus.ACCEPTED,
            eligibility_status=EligibilityStatus.ACTIVE,
        )

    for account_id, invitation in invitation_by_account.items():
        member = active_members.get(account_id)
        if member is not None:
            continue
        if any(row.account_id == account_id for row in members):
            raise SnapshotDataError(
                "an invitation account has an inactive room membership"
            )
        if invitation.response_status == "ACCEPTED":
            raise SnapshotDataError(
                "an accepted invitation must be connected to an active room member"
            )
        participant_by_account[account_id] = Participant(
            participant_id=account_id,
            display_name="Invitee",
            role=ParticipantRole.INVITEE,
            invitation_status=InvitationStatus.SENT,
            response_status=ResponseStatus(invitation.response_status),
            eligibility_status=EligibilityStatus(invitation.eligibility_status),
        )

    participants = tuple(
        participant_by_account[account_id]
        for account_id in sorted(participant_by_account)
    )
    eligible_count = sum(
        participant.role == ParticipantRole.ORGANIZER
        or (
            participant.response_status == ResponseStatus.ACCEPTED
            and participant.eligibility_status == EligibilityStatus.ACTIVE
        )
        for participant in participants
    )
    if eligible_count < 2:
        raise InsufficientParticipantsError(
            "at least two eligible participants are required"
        )
    if settings.minimum_attendee_count > eligible_count:
        raise SnapshotConfigurationError(
            "minimumAttendeeCount exceeds the eligible participant count"
        )

    member_ids = [member.id for member in active_members.values()]
    submissions: dict[str, ConditionSubmission] = {}
    if member_ids:
        rows = list(
            db.scalars(
                select(ConditionSubmission)
                .where(ConditionSubmission.room_member_id.in_(member_ids))
                .order_by(
                    ConditionSubmission.room_member_id,
                    ConditionSubmission.version.desc(),
                )
            )
        )
        for submission in rows:
            if type(submission.version) is not int or submission.version < 1:
                raise SnapshotDataError(
                    "condition submission version must be a positive integer"
                )
            submissions.setdefault(submission.room_member_id, submission)

    submission_ids = [submission.id for submission in submissions.values()]
    slots_by_submission: dict[str, list[ConditionAvailableSlot]] = defaultdict(list)
    if submission_ids:
        for slot in db.scalars(
            select(ConditionAvailableSlot)
            .where(ConditionAvailableSlot.condition_submission_id.in_(submission_ids))
            .order_by(ConditionAvailableSlot.starts_at, ConditionAvailableSlot.id)
        ):
            slots_by_submission[slot.condition_submission_id].append(slot)

    member_by_account = active_members
    availability: dict[str, AvailabilitySubmission] = {}
    allowed_dates = set(settings.dates)
    for participant in participants:
        member = member_by_account.get(participant.participant_id)
        submission = submissions.get(member.id) if member is not None else None
        if submission is None:
            availability[participant.participant_id] = AvailabilitySubmission(
                participant_id=participant.participant_id,
                status=AvailabilityStatus.NOT_SUBMITTED,
                slots=(),
                submission_version=0,
            )
            continue
        normalized_slots = _normalize_slots(
            slots_by_submission.get(submission.id, ()), allowed_dates
        )
        if not normalized_slots:
            raise SnapshotDataError(
                "the latest condition submission has no availability slots"
            )
        availability[participant.participant_id] = AvailabilitySubmission(
            participant_id=participant.participant_id,
            status=AvailabilityStatus.SUBMITTED,
            slots=normalized_slots,
            time_zone="Asia/Seoul",
            submitted_at=_to_utc(submission.submitted_at),
            submission_version=submission.version,
        )

    eligible_dates = tuple(sorted(settings.dates))
    excluded_dates = tuple(sorted(settings.excluded_dates))
    required_starts = dict(
        sorted(settings.required_start_minutes_by_date.items())
    )
    absolute_windows = tuple(
        AbsoluteTimeWindow(
            date=window.date,
            start_minute=window.start_minute,
            end_minute=window.end_minute,
        )
        for window in sorted(
            settings.absolute_time_windows,
            key=lambda item: (item.date, item.start_minute, item.end_minute),
        )
    )
    canonical = _canonical_hash_payload(
        room=room,
        settings=settings,
        participants=participants,
        availability=availability,
    )
    snapshot_hash = hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    try:
        return MeetingSnapshot(
            meeting_id=room.id,
            agent_session_id=agent_session_id,
            run_id=run_id,
            input_revision=room.agent_input_revision,
            input_snapshot_hash=snapshot_hash,
            consent_round=consent_round,
            title=room.title,
            activity=settings.activity,
            location=settings.location,
            duration_minutes=settings.duration_minutes,
            dates=eligible_dates,
            excluded_dates=excluded_dates,
            time_zone=settings.time_zone,
            minimum_attendee_count=settings.minimum_attendee_count,
            required_start_minutes_by_date=required_starts,
            absolute_time_windows=absolute_windows,
            participants=participants,
            availability_by_participant_id=availability,
        )
    except ValidationError as exc:
        raise SnapshotDataError(
            "v2.1 data is incompatible with the Agent MeetingSnapshot contract"
        ) from exc
