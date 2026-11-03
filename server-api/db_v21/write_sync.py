"""Keep JSON snapshots and normalized condition/proposal rows in sync on write."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from db_v21.models.condition import (
    ConditionAvailableSlot,
    ConditionRolePreference,
    ConditionSubmission,
)
from db_v21.models.proposal import (
    Proposal,
    ProposalAssignment,
    ProposalConditionInput,
)
from db_v21.models.room import RoomRole
from db_v21.base import now

# Meeting wall-clock times are Asia/Seoul; TIMESTAMPTZ stores the instant with offset.
SEOUL = ZoneInfo("Asia/Seoul")


def _interval_bounds(date_str: str, start_min: int, end_min: int) -> tuple[datetime, datetime]:
    day = datetime.fromisoformat(date_str).replace(tzinfo=SEOUL)
    return day + timedelta(minutes=int(start_min)), day + timedelta(minutes=int(end_min))


def wall_clock_seoul(dt: datetime) -> datetime:
    """Normalize a stored datetime to Asia/Seoul wall clock for assertions/display.

    PostgreSQL TIMESTAMPTZ returns an aware instant — convert with astimezone.
    SQLite strips tzinfo and keeps the written clock numbers; attach Seoul rather
    than calling astimezone on naive values (that would treat them as local/UTC).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SEOUL)
    return dt.astimezone(SEOUL)


def sync_condition_normalized(db, submission: ConditionSubmission, confirmed: dict, room_id: str) -> None:
    """Derive slots/preferences from the same payload stored in `confirmed`."""
    db.execute(
        delete(ConditionAvailableSlot).where(
            ConditionAvailableSlot.condition_submission_id == submission.id
        )
    )
    db.execute(
        delete(ConditionRolePreference).where(
            ConditionRolePreference.condition_submission_id == submission.id
        )
    )

    for interval in confirmed.get("availability") or []:
        starts_at, ends_at = _interval_bounds(interval["date"], interval["start"], interval["end"])
        if ends_at <= starts_at:
            continue
        db.add(
            ConditionAvailableSlot(
                condition_submission_id=submission.id,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )

    roles = {
        r.name: r.id
        for r in db.scalars(select(RoomRole).where(RoomRole.room_id == room_id))
    }
    # Priority: AVOID > PREFERRED (required/preferences) > AVAILABLE (capable roles)
    preference_by_role: dict[str, str] = {}
    for name in confirmed.get("roles") or []:
        if name in roles:
            preference_by_role[name] = "AVAILABLE"
    for name in confirmed.get("rolePreferences") or []:
        if name in roles:
            preference_by_role[name] = "PREFERRED"
    for name in confirmed.get("requiredRoles") or []:
        if name in roles:
            preference_by_role[name] = "PREFERRED"
    for name in confirmed.get("roleUnavailable") or []:
        if name in roles:
            preference_by_role[name] = "AVOID"

    for name, preference in preference_by_role.items():
        db.add(
            ConditionRolePreference(
                condition_submission_id=submission.id,
                room_role_id=roles[name],
                preference=preference,
                note=None,
            )
        )


def sync_proposal_normalized(db, proposal: Proposal, plan: dict, snapshot: dict) -> None:
    """Derive condition inputs + assignments from plan / snapshot; match JSON write."""
    db.execute(delete(ProposalConditionInput).where(ProposalConditionInput.proposal_id == proposal.id))
    db.execute(delete(ProposalAssignment).where(ProposalAssignment.proposal_id == proposal.id))

    versions = (snapshot or {}).get("versions") or {}
    for member_id, version in versions.items():
        submission = db.scalar(
            select(ConditionSubmission).where(
                ConditionSubmission.room_member_id == member_id,
                ConditionSubmission.version == version,
            )
        )
        if not submission:
            continue
        db.add(
            ProposalConditionInput(
                proposal_id=proposal.id,
                room_member_id=member_id,
                condition_submission_id=submission.id,
            )
        )

    roles = {
        r.name: r.id
        for r in db.scalars(select(RoomRole).where(RoomRole.room_id == proposal.room_id))
    }
    for item in plan.get("assignments") or []:
        role_name = item.get("role")
        member_id = item.get("participantId")
        interval = item.get("interval") or {}
        role_id = roles.get(role_name)
        if not role_id or not member_id or "date" not in interval:
            continue
        starts_at, ends_at = _interval_bounds(interval["date"], interval["start"], interval["end"])
        if ends_at <= starts_at:
            continue
        db.add(
            ProposalAssignment(
                proposal_id=proposal.id,
                room_member_id=member_id,
                room_role_id=role_id,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )


def invalidate_prior_proposals(db, room_id: str, keep_id: str) -> None:
    for row in db.scalars(
        select(Proposal).where(
            Proposal.room_id == room_id,
            Proposal.id != keep_id,
            Proposal.proposal_status != "INVALIDATED",
        )
    ):
        row.proposal_status = "INVALIDATED"
        row.invalidated_at = now()
