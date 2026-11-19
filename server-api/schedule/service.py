"""Schedule state transitions under rooms row lock."""
from __future__ import annotations

import os
import secrets
import threading
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from db_v21.base import now as utc_now
from db_v21.base import uid
from db_v21.models.room import Room, RoomMember
from db_v21.models.schedule import (
    ScheduleCandidate,
    ScheduleCandidateMember,
    ScheduleCollection,
    ScheduleResponse,
    ScheduleResponseRange,
    ScheduleResult,
    ScheduleRun,
    ScheduleVote,
    ScheduleVoteBallot,
)
from schedule.collection import (
    default_full_scope,
    near_misses,
    slot_availability_counts,
    validate_available_ranges,
)
from schedule.constants import (
    ALL_DONE_GRACE,
    CODE_ALPHABET,
    EXTENSION,
    INPUT_WINDOW,
    MAX_EXTENSIONS,
    MAX_READJUSTS,
    MIN_CANDIDATE_MINUTES,
    MIN_PEOPLE,
)
from schedule.coordination import Candidate, compute_candidates, prepare_voting_candidates
from schedule.deps import fail
from schedule.events import queue_event
from schedule.timeutil import (
    ceil_to_slot,
    format_iso,
    room_bounds_from_dates,
    seoul_now,
    seoul_today,
    to_seoul,
    validate_meeting_dates,
)


def _max_members() -> int | None:
    raw = os.getenv("MAX_MEMBERS")
    if not raw:
        return None
    return int(raw)


def _meeting_status(room: Room) -> str:
    if room.progress_status == "deleted":
        return "DELETED"
    if room.progress_status == "cancelled":
        return "FAILED"
    if room.progress_status == "finalized":
        return "CONFIRMED"
    if room.progress_status == "reviewing":
        return "VOTING"
    return "COLLECTING"


def _active_members(db, room_id: str) -> list[RoomMember]:
    return list(
        db.scalars(
            select(RoomMember).where(
                RoomMember.room_id == room_id,
                RoomMember.membership_status == "ACTIVE",
            )
        )
    )


def _open_collection(db, room_id: str) -> ScheduleCollection | None:
    return db.scalar(
        select(ScheduleCollection).where(
            ScheduleCollection.room_id == room_id,
            ScheduleCollection.status == "OPEN",
        )
    )


def _has_any_collection(db, room_id: str) -> bool:
    return (
        db.scalar(
            select(ScheduleCollection.id).where(ScheduleCollection.room_id == room_id).limit(1)
        )
        is not None
    )


def _is_legacy_room(db, room: Room) -> bool:
    return not _has_any_collection(db, room.id)


def _done_member_ids(db, collection_id: str) -> set[str]:
    rows = db.scalars(
        select(ScheduleResponse.room_member_id).where(
            ScheduleResponse.collection_id == collection_id
        )
    )
    return set(rows)


def _member_ranges(
    db, collection_id: str, member_ids: set[str] | None = None
) -> dict[str, list[tuple[datetime, datetime]]]:
    q = select(ScheduleResponseRange).where(
        ScheduleResponseRange.collection_id == collection_id
    )
    rows = list(db.scalars(q))
    out: dict[str, list[tuple[datetime, datetime]]] = {}
    for row in rows:
        if member_ids is not None and row.room_member_id not in member_ids:
            continue
        out.setdefault(row.room_member_id, []).append(
            (to_seoul(row.starts_at), to_seoul(row.ends_at))
        )
    return out


def _new_code(db) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if not db.scalar(select(Room.id).where(Room.code == code)):
            return code
    fail(500, "초대 코드를 만들지 못했습니다.")


def _open_new_collection(
    db,
    room: Room,
    *,
    cycle: int,
    kind: str,
    now: datetime,
) -> ScheduleCollection | None:
    """Open a collection. Returns None if remaining range is too short (marks cancelled)."""
    now_s = seoul_now(now)
    scope_start = max(to_seoul(room.starts_at), ceil_to_slot(now_s))
    scope_end = to_seoul(room.ends_at)
    if scope_end - scope_start < timedelta(minutes=MIN_CANDIDATE_MINUTES):
        room.progress_status = "cancelled"
        room.lifecycle_status = "CANCELLED"
        room.revision += 1
        db.flush()
        return None
    closes = min(now_s + INPUT_WINDOW, scope_end)
    col = ScheduleCollection(
        id=uid(),
        room_id=room.id,
        cycle=cycle,
        kind=kind,
        hints_enabled=(kind == "READJUST"),
        scope_starts_at=scope_start,
        scope_ends_at=scope_end,
        opened_at=now_s,
        closes_at=closes,
        grace_until=None,
        status="OPEN",
        extended_count=0,
    )
    db.add(col)
    room.progress_status = "collecting"
    room.lifecycle_status = "COLLECTING_CONDITIONS"
    room.revision += 1
    db.flush()
    return col


def create_meeting(db, account, body, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    try:
        validate_meeting_dates(body.start_date, body.end_date, now)
    except ValueError as exc:
        fail(422, str(exc))
    starts_at, ends_at = room_bounds_from_dates(body.start_date, body.end_date)
    room_id, member_id = uid(), uid()
    code = _new_code(db)
    room = Room(
        id=room_id,
        code=code,
        created_by_account_id=account.id,
        host_member_id=member_id,
        title=body.title,
        starts_at=starts_at,
        ends_at=ends_at,
        lifecycle_status="COLLECTING_CONDITIONS",
        progress_status="collecting",
        meeting_settings={
            "startDate": body.start_date.isoformat(),
            "endDate": body.end_date.isoformat(),
        },
        revision=1,
        dirty=False,
        current_round=0,
    )
    db.add(room)
    db.flush()
    db.add(
        RoomMember(
            id=member_id,
            room_id=room_id,
            account_id=account.id,
            nickname=body.nickname,
            room_role="OWNER",
            membership_status="ACTIVE",
        )
    )
    db.flush()
    col = _open_new_collection(db, room, cycle=0, kind="NORMAL", now=now)
    if col is None:
        fail(422, "조율할 수 있는 시간이 없어요.")
    queue_event(room.id, "collection_opened", room.revision)
    return meeting_view(db, room, account.id, now=now)


def join_meeting(db, account, body, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    room = db.scalar(
        select(Room).where(Room.code == body.code.upper()).with_for_update()
    )
    if not room or room.progress_status == "deleted" or room.deleted_at is not None:
        fail(404, "모임을 찾을 수 없습니다.")
    if _is_legacy_room(db, room):
        fail(409, "이전 앱 모임에는 참여할 수 없습니다.")
    close_collection_if_due(db, room.id, now)
    db.refresh(room)
    if room.progress_status in ("cancelled", "finalized", "reviewing", "deleted"):
        fail(409, "지금은 참여할 수 없습니다.")
    col = _open_collection(db, room.id)
    if not col:
        fail(409, "지금은 참여할 수 없습니다.")
    # Allow join while OPEN (including grace)
    existing = db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id, RoomMember.account_id == account.id
        )
    )
    if existing and existing.membership_status == "ACTIVE":
        return meeting_view(db, room, account.id, now=now)
    limit = _max_members()
    if limit is not None and len(_active_members(db, room.id)) >= limit:
        fail(409, "모임 인원이 가득 찼습니다.")
    # Nickname unique
    taken = db.scalar(
        select(RoomMember.id).where(
            RoomMember.room_id == room.id, RoomMember.nickname == body.nickname
        )
    )
    if taken:
        fail(409, "이미 사용 중인 닉네임입니다.")
    db.add(
        RoomMember(
            id=uid(),
            room_id=room.id,
            account_id=account.id,
            nickname=body.nickname,
            room_role="MEMBER",
            membership_status="ACTIVE",
        )
    )
    # Cancel grace if all-done was broken
    if col.grace_until is not None:
        col.grace_until = None
    room.revision += 1
    db.flush()
    queue_event(room.id, "member_joined", room.revision)
    return meeting_view(db, room, account.id, now=now)


def meeting_view(db, room: Room, account_id: str, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    close_collection_if_due(db, room.id, now)
    close_voting_if_due(db, room.id, now)
    db.refresh(room)
    members = _active_members(db, room.id)
    me = next((m for m in members if m.account_id == account_id), None)
    col = _open_collection(db, room.id)
    return {
        "id": room.id,
        "code": room.code,
        "title": room.title,
        "status": _meeting_status(room),
        "revision": room.revision,
        "startsAt": format_iso(room.starts_at),
        "endsAt": format_iso(room.ends_at),
        "serverTime": format_iso(seoul_now(now)),
        "timezone": "Asia/Seoul",
        "legacy": _is_legacy_room(db, room),
        "collectionId": col.id if col else None,
        "members": [
            {
                "id": m.id,
                "nickname": m.nickname,
                "role": m.room_role,
                "done": bool(
                    col
                    and db.get(ScheduleResponse, (col.id, m.id)) is not None
                ),
            }
            for m in members
        ],
        "myMemberId": me.id if me else None,
    }


def collection_view(db, room: Room, member: RoomMember, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    close_collection_if_due(db, room.id, now)
    db.refresh(room)
    col = _open_collection(db, room.id)
    if not col:
        # Maybe just closed — return latest closed for read
        col = db.scalar(
            select(ScheduleCollection)
            .where(ScheduleCollection.room_id == room.id)
            .order_by(ScheduleCollection.cycle.desc())
            .limit(1)
        )
        if not col:
            fail(404, "입력 기간이 없습니다.")
    members = _active_members(db, room.id)
    done_ids = _done_member_ids(db, col.id)
    ranges = _member_ranges(db, col.id, done_ids if done_ids else None)
    my_ranges = _member_ranges(db, col.id, {member.id}).get(member.id, [])
    # Prefill from previous cycles on READJUST if no current response
    if col.kind == "READJUST" and not my_ranges:
        my_ranges = _prefill_ranges(db, room.id, member.id, col)
    counts = slot_availability_counts(
        ranges,
        scope_starts_at=col.scope_starts_at,
        scope_ends_at=col.scope_ends_at,
        now=now,
    )
    hints: list[dict] = []
    if col.hints_enabled:
        hints = near_misses(
            ranges,
            scope_starts_at=col.scope_starts_at,
            scope_ends_at=col.scope_ends_at,
            now=now,
            viewer_member_id=member.id,
        )
    return {
        "id": col.id,
        "cycle": col.cycle,
        "kind": col.kind,
        "status": col.status,
        "scopeStartsAt": format_iso(col.scope_starts_at),
        "scopeEndsAt": format_iso(col.scope_ends_at),
        "closesAt": format_iso(col.closes_at),
        "graceUntil": format_iso(col.grace_until) if col.grace_until else None,
        "extendedCount": col.extended_count,
        "doneCount": len(done_ids),
        "memberCount": len(members),
        "myAvailable": [
            {"start": format_iso(s), "end": format_iso(e)} for s, e in my_ranges
        ],
        "slotCounts": counts,
        "nearMisses": hints,
        "revision": room.revision,
        "serverTime": format_iso(seoul_now(now)),
    }


def _prefill_ranges(db, room_id: str, member_id: str, col: ScheduleCollection):
    prev = list(
        db.scalars(
            select(ScheduleCollection)
            .where(
                ScheduleCollection.room_id == room_id,
                ScheduleCollection.cycle < col.cycle,
            )
            .order_by(ScheduleCollection.cycle)
        )
    )
    merged: list[tuple[datetime, datetime]] = []
    for p in prev:
        for s, e in _member_ranges(db, p.id, {member_id}).get(member_id, []):
            if e <= to_seoul(col.scope_starts_at):
                continue
            merged.append((max(s, to_seoul(col.scope_starts_at)), min(e, to_seoul(col.scope_ends_at))))
    return [(s, e) for s, e in merged if e > s]


def submit_response(
    db,
    room: Room,
    member: RoomMember,
    collection_id: str,
    available: list[tuple[datetime, datetime]],
    *,
    now: datetime | None = None,
) -> dict:
    now = now or utc_now()
    close_collection_if_due(db, room.id, now)
    close_voting_if_due(db, room.id, now)
    db.refresh(room)
    if room.progress_status in ("finalized", "cancelled", "reviewing", "deleted"):
        fail(409, "지금은 입력할 수 없습니다.")
    if db.get(ScheduleResult, room.id):
        fail(409, "확정된 모임은 변경할 수 없습니다.")
    col = db.scalar(
        select(ScheduleCollection)
        .where(ScheduleCollection.id == collection_id)
        .with_for_update()
    )
    if not col or col.room_id != room.id:
        fail(404, "입력 기간이 없습니다.")
    if col.status != "OPEN":
        fail(409, "입력이 마감되었습니다.")
    if _is_legacy_room(db, room):
        fail(409, "이전 앱 모임에서는 입력할 수 없습니다.")

    try:
        if not available:
            ranges = default_full_scope(col.scope_starts_at, col.scope_ends_at, now)
        else:
            ranges = validate_available_ranges(
                available,
                scope_starts_at=col.scope_starts_at,
                scope_ends_at=col.scope_ends_at,
            )
    except ValueError as exc:
        fail(422, str(exc))

    members = _active_members(db, room.id)
    done_before = _done_member_ids(db, col.id)
    was_all_done = len(members) >= MIN_PEOPLE and done_before >= {m.id for m in members}

    # Replace ranges
    db.execute(
        delete(ScheduleResponseRange).where(
            ScheduleResponseRange.collection_id == col.id,
            ScheduleResponseRange.room_member_id == member.id,
        )
    )
    resp = db.get(ScheduleResponse, (col.id, member.id))
    if resp:
        resp.submitted_at = seoul_now(now)
    else:
        db.add(
            ScheduleResponse(
                collection_id=col.id,
                room_member_id=member.id,
                submitted_at=seoul_now(now),
            )
        )
    for s, e in ranges:
        db.add(
            ScheduleResponseRange(
                id=uid(),
                collection_id=col.id,
                room_member_id=member.id,
                starts_at=s,
                ends_at=e,
            )
        )
    db.flush()

    done_after = _done_member_ids(db, col.id)
    active_ids = {m.id for m in members}
    all_done = len(members) >= MIN_PEOPLE and done_after >= active_ids
    grace_started = False
    if all_done and not was_all_done:
        col.grace_until = seoul_now(now) + ALL_DONE_GRACE
        grace_started = True
    # else: keep grace (including resubmit while already all-done)
    room.revision += 1
    db.flush()
    queue_event(room.id, "response_submitted", room.revision)
    if grace_started:
        queue_event(room.id, "grace_started", room.revision)
    close_collection_if_due(db, room.id, now)
    db.refresh(room)
    return collection_view(db, room, member, now=now)


def close_collection_if_due(db, room_id: str, now: datetime | None = None) -> bool:
    """Idempotent close / extend / coordinate. Returns True if a transition ran."""
    now = now or utc_now()
    now_s = seoul_now(now)
    room = db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if not room or room.progress_status in ("deleted", "cancelled", "finalized"):
        return False
    if room.progress_status == "reviewing":
        return False
    col = _open_collection(db, room.id)
    if not col:
        return False

    deadline = to_seoul(col.closes_at)
    grace = to_seoul(col.grace_until) if col.grace_until else None
    due_grace = grace is not None and now_s >= grace
    due_deadline = now_s >= deadline
    if not due_grace and not due_deadline:
        return False

    # Prefer whichever fires; if both, use earlier reason: closes_at wins if earlier
    if due_deadline and (grace is None or deadline <= grace):
        reason = "DEADLINE"
    else:
        reason = "ALL_DONE"

    members = _active_members(db, room.id)
    done_ids = _done_member_ids(db, col.id)
    done_count = len(done_ids)

    if done_count < MIN_PEOPLE:
        if col.extended_count < MAX_EXTENSIONS:
            new_closes = min(deadline + EXTENSION, to_seoul(room.ends_at))
            if new_closes > deadline:
                col.closes_at = new_closes
                col.extended_count = 1
                col.grace_until = None
                room.revision += 1
                db.flush()
                return True
        # Cannot extend → fail
        col.status = "CLOSED"
        col.closed_at = now_s
        col.closed_reason = reason
        col.grace_until = None
        room.progress_status = "cancelled"
        room.lifecycle_status = "CANCELLED"
        room.revision += 1
        db.flush()
        queue_event(room.id, "collection_closed", room.revision)
        return True

    # Close and coordinate
    col.status = "CLOSED"
    col.closed_at = now_s
    col.closed_reason = reason
    col.grace_until = None
    db.flush()
    queue_event(room.id, "collection_closed", room.revision)
    run_coordination(db, room, col, done_ids, now=now_s)
    return True


def run_coordination(
    db,
    room: Room,
    col: ScheduleCollection,
    done_ids: set[str],
    *,
    now: datetime,
) -> None:
    ranges = _member_ranges(db, col.id, done_ids)
    candidates = compute_candidates(
        ranges,
        now=now,
        scope_starts_at=col.scope_starts_at,
        scope_ends_at=col.scope_ends_at,
    )
    run = ScheduleRun(
        id=uid(),
        room_id=room.id,
        collection_id=col.id,
        max_count=max((c.available_count for c in candidates), default=0),
        participant_count=len(done_ids),
        voter_count=len(done_ids),
        excluded_soon_count=0,
        created_at=now,
    )
    db.add(run)
    db.flush()

    def persist(cands: list[Candidate]) -> list[ScheduleCandidate]:
        rows: list[ScheduleCandidate] = []
        for idx, c in enumerate(cands, start=1):
            row = ScheduleCandidate(
                id=uid(),
                run_id=run.id,
                room_id=room.id,
                starts_at=c.starts_at,
                ends_at=c.ends_at,
                available_count=c.available_count,
                sort_order=idx,
            )
            db.add(row)
            db.flush()
            for mid in c.member_ids:
                db.add(
                    ScheduleCandidateMember(
                        candidate_id=row.id, room_member_id=mid
                    )
                )
            rows.append(row)
        return rows

    if not candidates:
        _handle_zero_candidates(db, room, col, now)
        return

    if len(candidates) == 1:
        rows = persist(candidates)
        _confirm(db, room, rows[0], method="AUTO", now=now)
        queue_event(room.id, "coordinated", room.revision)
        queue_event(room.id, "confirmed", room.revision)
        _enqueue_summary_after_flush(run.id)
        return

    remaining, voting_ends, excluded = prepare_voting_candidates(candidates, now=now)
    run.excluded_soon_count = excluded
    if len(remaining) == 0:
        _handle_zero_candidates(db, room, col, now)
        return
    if len(remaining) == 1:
        rows = persist(remaining)
        _confirm(db, room, rows[0], method="AUTO", now=now)
        queue_event(room.id, "coordinated", room.revision)
        queue_event(room.id, "confirmed", room.revision)
        _enqueue_summary_after_flush(run.id)
        return

    rows = persist(remaining)
    run.voting_started_at = now
    run.voting_ends_at = voting_ends
    room.progress_status = "reviewing"
    room.lifecycle_status = "WAITING_FOR_CONSENT"
    room.revision += 1
    db.flush()
    queue_event(room.id, "coordinated", room.revision)
    queue_event(room.id, "voting_started", room.revision)
    _enqueue_summary_after_flush(run.id)


def _enqueue_summary_after_flush(run_id: str) -> None:
    """Fire-and-forget Qwen explanation; must not affect coordination outcome."""
    from schedule.ai_summary import enqueue_ai_summary

    enqueue_ai_summary(run_id)


def _confirm(
    db,
    room: Room,
    candidate: ScheduleCandidate,
    *,
    method: str,
    now: datetime,
    vote_count: int | None = None,
    tie_broken: bool = False,
) -> None:
    if db.get(ScheduleResult, room.id):
        return  # idempotent
    from sqlalchemy.exc import IntegrityError

    try:
        with db.begin_nested():
            db.add(
                ScheduleResult(
                    room_id=room.id,
                    candidate_id=candidate.id,
                    method=method,
                    vote_count=vote_count,
                    tie_broken=tie_broken,
                    confirmed_at=now,
                )
            )
            room.progress_status = "finalized"
            room.lifecycle_status = "CONFIRMED"
            room.revision += 1
            db.flush()
    except IntegrityError:
        # Concurrent confirm won the UNIQUE(room_id) race
        db.refresh(room)
        return
    # Caller may also emit confirmed for AUTO; VOTE path emits after close.


def _latest_voting_run(db, room_id: str) -> ScheduleRun | None:
    return db.scalar(
        select(ScheduleRun)
        .where(
            ScheduleRun.room_id == room_id,
            ScheduleRun.voting_ends_at.is_not(None),
            ScheduleRun.closed_at.is_(None),
        )
        .order_by(ScheduleRun.created_at.desc())
        .limit(1)
    )


def close_voting_if_due(db, room_id: str, now: datetime | None = None) -> bool:
    """Idempotent voting close + confirm. Safe under rooms FOR UPDATE."""
    now = now or utc_now()
    now_s = seoul_now(now)
    room = db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if not room or room.progress_status != "reviewing":
        return False
    if db.get(ScheduleResult, room.id):
        return False
    run = _latest_voting_run(db, room.id)
    if not run or run.voting_ends_at is None:
        return False

    from sqlalchemy import func

    ballot_count = (
        db.scalar(
            select(func.count())
            .select_from(ScheduleVoteBallot)
            .where(ScheduleVoteBallot.run_id == run.id)
        )
        or 0
    )
    voters = run.voter_count or run.participant_count or 0
    all_voted = voters > 0 and ballot_count >= voters
    timed_out = now_s >= to_seoul(run.voting_ends_at)
    if not all_voted and not timed_out:
        return False

    reason = "ALL_VOTED" if all_voted else "TIMEOUT"
    cands = list(
        db.scalars(
            select(ScheduleCandidate)
            .where(ScheduleCandidate.run_id == run.id)
            .order_by(ScheduleCandidate.sort_order)
        )
    )
    if not cands:
        room.progress_status = "cancelled"
        room.lifecycle_status = "CANCELLED"
        run.closed_at = now_s
        run.closed_reason = reason
        room.revision += 1
        db.flush()
        queue_event(room.id, "voting_closed", room.revision)
        return True

    counts = {}
    for c in cands:
        counts[c.id] = (
            db.scalar(
                select(func.count())
                .select_from(ScheduleVote)
                .where(ScheduleVote.candidate_id == c.id)
            )
            or 0
        )
    max_votes = max(counts.values()) if counts else 0
    tied = [c for c in cands if counts[c.id] == max_votes]
    # 0 votes → sort_order 1; else plurality then lowest sort_order
    if max_votes == 0:
        winner = min(cands, key=lambda c: c.sort_order)
        tie_broken = len(cands) > 1
    else:
        winner = min(tied, key=lambda c: c.sort_order)
        tie_broken = len(tied) > 1

    run.closed_at = now_s
    run.closed_reason = reason
    _confirm(
        db,
        room,
        winner,
        method="VOTE",
        now=now_s,
        vote_count=counts[winner.id],
        tie_broken=tie_broken,
    )
    queue_event(room.id, "voting_closed", room.revision)
    queue_event(room.id, "confirmed", room.revision)
    return True


def submit_votes(
    db,
    room: Room,
    member: RoomMember,
    candidate_ids: list[str],
    *,
    now: datetime | None = None,
) -> dict:
    now = now or utc_now()
    now_s = seoul_now(now)
    room = db.scalar(select(Room).where(Room.id == room.id).with_for_update())
    if not room:
        fail(404, "모임을 찾을 수 없습니다.")
    if db.get(ScheduleResult, room.id) or room.progress_status == "finalized":
        fail(409, "확정된 모임은 변경할 수 없습니다.")
    close_voting_if_due(db, room.id, now)
    db.refresh(room)
    if room.progress_status != "reviewing":
        fail(409, "투표 기간이 아닙니다.")

    run = _latest_voting_run(db, room.id)
    if not run:
        fail(409, "투표 기간이 아닙니다.")
    if now_s >= to_seoul(run.voting_ends_at):
        close_voting_if_due(db, room.id, now)
        fail(409, "투표가 마감되었습니다.")

    # Eligibility: input completer for this run's collection
    if not run.collection_id or not db.get(
        ScheduleResponse, (run.collection_id, member.id)
    ):
        fail(403, "투표 대상자가 아닙니다.")

    # Validate candidates
    run_cands = {
        c.id: c
        for c in db.scalars(
            select(ScheduleCandidate).where(ScheduleCandidate.run_id == run.id)
        )
    }
    unique_ids = list(dict.fromkeys(candidate_ids))  # preserve order, dedupe
    for cid in unique_ids:
        if cid not in run_cands:
            fail(422, "선택할 수 없는 후보입니다.")
        allowed = db.get(ScheduleCandidateMember, (cid, member.id))
        if not allowed:
            fail(422, "참석할 수 없는 후보입니다.")

    # Replace votes for this member on this run
    for cid in run_cands:
        db.execute(
            delete(ScheduleVote).where(
                ScheduleVote.candidate_id == cid,
                ScheduleVote.room_member_id == member.id,
            )
        )
    ballot = db.get(ScheduleVoteBallot, (run.id, member.id))
    if ballot:
        ballot.submitted_at = now_s
    else:
        db.add(
            ScheduleVoteBallot(
                run_id=run.id, room_member_id=member.id, submitted_at=now_s
            )
        )
    for cid in unique_ids:
        db.add(
            ScheduleVote(
                candidate_id=cid,
                room_member_id=member.id,
                room_id=room.id,
                voted_at=now_s,
            )
        )
    room.revision += 1
    db.flush()
    queue_event(room.id, "vote_updated", room.revision)
    close_voting_if_due(db, room.id, now)
    db.refresh(room)
    return candidates_view(db, room, now=now, member_id=member.id)


def _handle_zero_candidates(
    db, room: Room, col: ScheduleCollection, now: datetime
) -> None:
    next_cycle = col.cycle + 1
    remaining = to_seoul(room.ends_at) - seoul_now(now)
    if next_cycle > MAX_READJUSTS or remaining < timedelta(minutes=MIN_CANDIDATE_MINUTES):
        room.progress_status = "cancelled"
        room.lifecycle_status = "CANCELLED"
        room.revision += 1
        db.flush()
        return
    opened = _open_new_collection(db, room, cycle=next_cycle, kind="READJUST", now=now)
    if opened is not None:
        queue_event(room.id, "readjust_opened", room.revision)
        queue_event(room.id, "collection_opened", room.revision)


def candidates_view(
    db, room: Room, *, now: datetime | None = None, member_id: str | None = None
) -> dict:
    from sqlalchemy import func

    now = now or utc_now()
    close_collection_if_due(db, room.id, now)
    close_voting_if_due(db, room.id, now)
    db.refresh(room)
    run = db.scalar(
        select(ScheduleRun)
        .where(ScheduleRun.room_id == room.id)
        .order_by(ScheduleRun.created_at.desc())
        .limit(1)
    )
    if not run:
        return {
            "candidates": [],
            "status": _meeting_status(room),
            "revision": room.revision,
            "aiSummary": None,
            "votingEndsAt": None,
            "excludedSoonCount": 0,
            "myBallotSubmitted": False,
        }
    cands = list(
        db.scalars(
            select(ScheduleCandidate)
            .where(ScheduleCandidate.run_id == run.id)
            .order_by(ScheduleCandidate.sort_order)
        )
    )
    members = {m.id: m for m in _active_members(db, room.id)}
    my_ballot = False
    if member_id:
        my_ballot = (
            db.get(ScheduleVoteBallot, (run.id, member_id)) is not None
        )
    out = []
    for c in cands:
        mids = list(
            db.scalars(
                select(ScheduleCandidateMember.room_member_id).where(
                    ScheduleCandidateMember.candidate_id == c.id
                )
            )
        )
        vote_count = (
            db.scalar(
                select(func.count())
                .select_from(ScheduleVote)
                .where(ScheduleVote.candidate_id == c.id)
            )
            or 0
        )
        out.append(
            {
                "id": c.id,
                "startsAt": format_iso(c.starts_at),
                "endsAt": format_iso(c.ends_at),
                "availableCount": c.available_count,
                "sortOrder": c.sort_order,
                "voteCount": vote_count,
                "memberNicknames": [
                    members[mid].nickname for mid in mids if mid in members
                ],
            }
        )
    return {
        "runId": run.id,
        "candidates": out,
        "status": _meeting_status(room),
        "revision": room.revision,
        "aiSummary": run.ai_summary,
        "votingEndsAt": format_iso(run.voting_ends_at) if run.voting_ends_at else None,
        "excludedSoonCount": run.excluded_soon_count,
        "myBallotSubmitted": my_ballot,
        "closedReason": run.closed_reason,
        "serverTime": format_iso(seoul_now(now)),
    }


def result_view(db, room: Room, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    close_voting_if_due(db, room.id, now)
    db.refresh(room)
    result = db.get(ScheduleResult, room.id)
    if not result:
        fail(404, "확정된 결과가 없습니다.")
    cand = db.get(ScheduleCandidate, result.candidate_id)
    return {
        "method": result.method,
        "voteCount": result.vote_count,
        "tieBroken": result.tie_broken,
        "confirmedAt": format_iso(result.confirmed_at),
        "candidate": {
            "id": cand.id,
            "startsAt": format_iso(cand.starts_at),
            "endsAt": format_iso(cand.ends_at),
            "availableCount": cand.available_count,
            "sortOrder": cand.sort_order,
        },
        "status": _meeting_status(room),
        "revision": room.revision,
    }


def server_time_payload(now: datetime | None = None) -> dict:
    now = now or utc_now()
    today = seoul_today(now)
    from schedule.timeutil import add_calendar_months

    return {
        "serverTime": format_iso(seoul_now(now)),
        "timezone": "Asia/Seoul",
        "maxEndDate": add_calendar_months(today, 1).isoformat(),
    }


_SWEEP_SERIALIZE = threading.RLock()


def sweep(*, now: datetime | None = None) -> int:
    """Close due collections (grace/24h) and voting windows. Idempotent; safe to overlap.

    PostgreSQL: overlapping callers are safe via per-room transactions + IntegrityError.
    SQLite (CI StaticPool): serialize the whole sweep — SQLite cannot run concurrent
    writers on one in-memory connection without InterfaceError / duplicate runs.
    """
    import os

    from sqlalchemy import and_, or_
    from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError

    from database import session as db_session_factory
    from schedule.events import drain_pending, publish_pending_sync

    now = now or utc_now()
    now_s = seoul_now(now)
    url = os.getenv("DATABASE_URL") or ""
    serialize = url.startswith("sqlite")
    if serialize:
        _SWEEP_SERIALIZE.acquire()
    try:
        with db_session_factory() as db:
            due_collections = list(
                db.scalars(
                    select(ScheduleCollection.room_id).where(
                        ScheduleCollection.status == "OPEN",
                        or_(
                            ScheduleCollection.closes_at <= now_s,
                            and_(
                                ScheduleCollection.grace_until.is_not(None),
                                ScheduleCollection.grace_until <= now_s,
                            ),
                        ),
                    )
                )
            )
            due_votes = list(
                db.scalars(
                    select(ScheduleRun.room_id).where(
                        ScheduleRun.closed_at.is_(None),
                        ScheduleRun.voting_ends_at.is_not(None),
                        ScheduleRun.voting_ends_at <= now_s,
                    )
                )
            )
        room_ids = list(dict.fromkeys([*due_collections, *due_votes]))
        changed = 0
        for room_id in room_ids:
            try:
                with db_session_factory() as db, db.begin():
                    did = False
                    if close_collection_if_due(db, room_id, now=now):
                        did = True
                    if close_voting_if_due(db, room_id, now=now):
                        did = True
                    if did:
                        changed += 1
                publish_pending_sync()
            except IntegrityError:
                # Concurrent sweeper already confirmed — treat as idempotent no-op
                drain_pending()
                continue
            except (InterfaceError, OperationalError):
                # SQLite lock / StaticPool races under overlapping callers
                drain_pending()
                if serialize:
                    continue
                raise
            except Exception:
                drain_pending()
                raise
        return changed
    finally:
        if serialize:
            _SWEEP_SERIALIZE.release()
