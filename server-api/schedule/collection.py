"""Collection helpers: range validation, slot counts, near-miss hints."""
from __future__ import annotations

from datetime import datetime, timedelta

from schedule.constants import MAX_HINTS, MIN_CANDIDATE_MINUTES, MIN_PEOPLE, SLOT_MINUTES
from schedule.timeutil import ceil_to_slot, format_iso, is_slot_aligned, to_seoul


def validate_available_ranges(
    ranges: list[tuple[datetime, datetime]],
    *,
    scope_starts_at: datetime,
    scope_ends_at: datetime,
) -> list[tuple[datetime, datetime]]:
    scope_start = to_seoul(scope_starts_at)
    scope_end = to_seoul(scope_ends_at)
    cleaned: list[tuple[datetime, datetime]] = []
    for start, end in ranges:
        s, e = to_seoul(start), to_seoul(end)
        if e <= s:
            raise ValueError("종료는 시작 이후여야 합니다.")
        if not is_slot_aligned(s) or not is_slot_aligned(e):
            raise ValueError("30분 단위 시간을 입력해 주세요.")
        if s < scope_start or e > scope_end:
            raise ValueError("모임 날짜 범위 안의 시간만 제출해 주세요.")
        cleaned.append((s, e))
    # Merge overlapping / adjacent for storage stability (optional but helpful)
    cleaned.sort(key=lambda x: x[0])
    merged: list[tuple[datetime, datetime]] = []
    for s, e in cleaned:
        if not merged or s > merged[-1][1]:
            merged.append((s, e))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    return merged


def default_full_scope(
    scope_starts_at: datetime, scope_ends_at: datetime, now: datetime
) -> list[tuple[datetime, datetime]]:
    """Entire remaining scope as available (default when client sends empty unavailable)."""
    start = max(to_seoul(scope_starts_at), ceil_to_slot(now))
    end = to_seoul(scope_ends_at)
    if end <= start:
        return []
    # Align start/end to slots
    if not is_slot_aligned(start):
        start = ceil_to_slot(start)
    return [(start, end)] if end > start else []


def slot_availability_counts(
    member_ranges: dict[str, list[tuple[datetime, datetime]]],
    *,
    scope_starts_at: datetime,
    scope_ends_at: datetime,
    now: datetime,
) -> list[dict]:
    """Per 30-min slot: {start, end, count} with no member ids (Q37)."""
    cutoff = max(ceil_to_slot(now), to_seoul(scope_starts_at))
    end = to_seoul(scope_ends_at)
    out: list[dict] = []
    slot = cutoff
    while slot + timedelta(minutes=SLOT_MINUTES) <= end:
        slot_end = slot + timedelta(minutes=SLOT_MINUTES)
        count = 0
        for ranges in member_ranges.values():
            if any(s <= slot and e >= slot_end for s, e in ranges):
                count += 1
        out.append(
            {
                "start": format_iso(slot),
                "end": format_iso(slot_end),
                "count": count,
            }
        )
        slot = slot_end
    return out


def near_misses(
    member_ranges: dict[str, list[tuple[datetime, datetime]]],
    *,
    scope_starts_at: datetime,
    scope_ends_at: datetime,
    now: datetime,
    viewer_member_id: str | None = None,
) -> list[dict]:
    """Hint rows with counts only (no nicknames)."""
    from schedule.coordination import compute_candidates

    # Reuse slot sets via a lightweight scan: look for almost-candidates
    hints: list[dict] = []
    # Time-short: 2+ overlap but < 60m — scan contiguous stretches
    cutoff = max(ceil_to_slot(now), to_seoul(scope_starts_at))
    end = to_seoul(scope_ends_at)
    # Build per-slot member sets
    slots: list[tuple[datetime, frozenset[str]]] = []
    slot = cutoff
    while slot + timedelta(minutes=SLOT_MINUTES) <= end:
        slot_end = slot + timedelta(minutes=SLOT_MINUTES)
        present = frozenset(
            mid
            for mid, ranges in member_ranges.items()
            if any(s <= slot and e >= slot_end for s, e in ranges)
        )
        slots.append((slot, present))
        slot = slot_end

    # Stretches with same intersection size patterns
    i = 0
    while i < len(slots):
        start_slot, people = slots[i]
        if len(people) < 1:
            i += 1
            continue
        j = i
        inter = set(people)
        while j + 1 < len(slots):
            nxt = slots[j + 1]
            if nxt[0] - slots[j][0] != timedelta(minutes=SLOT_MINUTES):
                break
            new_inter = inter & set(nxt[1])
            if not new_inter:
                break
            # allow shrinking
            inter = new_inter
            j += 1
        end_slot = slots[j][0] + timedelta(minutes=SLOT_MINUTES)
        duration = end_slot - start_slot
        count = len(inter)
        if count >= MIN_PEOPLE and duration < timedelta(minutes=MIN_CANDIDATE_MINUTES):
            need = MIN_CANDIDATE_MINUTES - int(duration.total_seconds() // 60)
            msg = (
                f"{start_slot.month}/{start_slot.day} "
                f"{start_slot:%H:%M}–{end_slot:%H:%M} {count}명이 겹쳐요. "
                f"{need}분만 더 되면 후보가 돼요"
            )
            viewer_missing = viewer_member_id is not None and viewer_member_id not in inter
            hints.append(
                {
                    "kind": "TIME",
                    "start": format_iso(start_slot),
                    "end": format_iso(end_slot),
                    "count": count,
                    "message": ("내가 되면 후보가 돼요. " + msg) if viewer_missing else msg,
                }
            )
        elif count == 1 and duration >= timedelta(minutes=MIN_CANDIDATE_MINUTES):
            msg = (
                f"{start_slot.month}/{start_slot.day} "
                f"{start_slot:%H:%M}–{end_slot:%H:%M} 1명만 돼요. "
                f"한 명만 더 되면 후보가 돼요"
            )
            viewer_in = viewer_member_id is not None and viewer_member_id in inter
            hints.append(
                {
                    "kind": "PEOPLE",
                    "start": format_iso(start_slot),
                    "end": format_iso(end_slot),
                    "count": 1,
                    "message": msg if viewer_in else ("내가 되면 후보가 돼요. " + msg),
                }
            )
        i = j + 1

    # Prefer smaller change then earlier time; drop if already real candidates dominate
    real = compute_candidates(
        member_ranges,
        now=now,
        scope_starts_at=scope_starts_at,
        scope_ends_at=scope_ends_at,
    )
    if real:
        return []
    hints.sort(key=lambda h: (0 if h["kind"] == "TIME" else 1, h["start"]))
    return hints[:MAX_HINTS]
