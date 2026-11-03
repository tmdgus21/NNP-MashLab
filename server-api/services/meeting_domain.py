"""Meeting-domain boundary between /v1 role assignment and Potato Meet (Agent).

A room is a Potato Meet room when ``meeting_settings`` carries a
``coordination`` block -- the contract services.meeting_snapshot already
requires. Rooms created through /v1 never have it, so every guard here is a
no-op for them. There is no explicit type column (open question in the report).

Two different "round" counters exist and must not be confused:
- ``rooms.current_round``       /v1 role-plan round (bumped by every /v1 calculation)
- ``rooms.coordination_round``  Potato Meet round (bumped only by an explicit
                                host action: services.coordination_round)
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.agent import AgentCandidate, AgentRun
from db_v21.models.room import Room

# Runs whose candidates/consents/approvals depend on the input being replaced.
# RUNNING Runs are left to the Worker, which revalidates before persisting.
SUPERSEDABLE_STATUSES = (
    "QUEUED", "WAITING_FOR_INPUT", "ANALYZING", "RUNNING_TOOLS", "ALL_AVAILABLE",
    "PARTIAL_ALTERNATIVE", "NO_FEASIBLE_SCHEDULE", "AWAITING_APPROVAL",
)


def is_potato_meet(room: Room) -> bool:
    settings = room.meeting_settings
    return isinstance(settings, dict) and "coordination" in settings


def agent_final_exists(db: Session, room: Room) -> bool:
    """True when the room's CURRENT coordination round already has a final result."""
    return (
        db.scalar(
            select(AgentRun.id).where(
                AgentRun.room_id == room.id,
                AgentRun.finalized_at.is_not(None),
                AgentRun.finalized_room_round == room.coordination_round,
            )
        )
        is not None
    )


def bump_agent_input_revision(room: Room) -> None:
    """Advance the Agent input revision for a Potato Meet room; no-op for /v1 rooms."""
    if is_potato_meet(room):
        room.agent_input_revision += 1


def supersede_open_runs(db: Session, room_id: str, detail: str) -> None:
    """Mark every undecided-or-in-decision Run STALE. Finalized Runs and all
    candidate/consent/approval rows are left exactly as they are (history)."""
    db.execute(
        update(AgentRun)
        .where(
            AgentRun.room_id == room_id,
            AgentRun.status.in_(SUPERSEDABLE_STATUSES),
            AgentRun.finalized_at.is_(None),
        )
        .values(
            status="STALE",
            error_code="STALE_AGENT_RUN",
            error_detail=detail,
            completed_at=now(),
        )
        .execution_options(synchronize_session=False)
    )


def record_input_change(db: Session, room: Room, detail: str) -> None:
    """One call for every Agent-input change on a Potato Meet room (the caller
    holds the room row lock): advance both revision counters and invalidate every
    open Run in the same transaction. Finalized Runs and all history stay as is."""
    room.agent_input_revision += 1
    room.revision += 1
    supersede_open_runs(db, room.id, detail)


def potato_deadline(db: Session, room: Room):
    """Lifecycle schedule for a Potato Meet room: (scheduled ISO date, actual end or None).

    Uses the coordination dates (the active ones when any remain) instead of the
    /v1 ``config['dates']``; once the current round has a final result, the
    finalized candidate's day and end time decide when the cycle closes.
    """
    coordination = room.meeting_settings["coordination"]
    dates = sorted(set(coordination.get("dates") or ()) - set(coordination.get("excludedDates") or ()))
    dates = dates or sorted(coordination.get("dates") or ["1970-01-01"])
    scheduled, actual = dates[-1], None
    final = db.scalar(
        select(AgentRun).where(
            AgentRun.room_id == room.id,
            AgentRun.finalized_at.is_not(None),
            AgentRun.finalized_room_round == room.coordination_round,
        )
    )
    if final is not None and final.selected_candidate_id:
        candidate = db.get(AgentCandidate, final.selected_candidate_id)
        if candidate is not None:
            scheduled = candidate.meeting_date.isoformat()
            actual = candidate.ends_at
            if actual.tzinfo is None:  # SQLite keeps the Seoul wall clock without tzinfo
                actual = actual.replace(tzinfo=ZoneInfo("Asia/Seoul"))
    return scheduled, actual
