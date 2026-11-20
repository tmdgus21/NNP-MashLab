"""Pure candidate computation (coordination-algorithm.md §4). No OR-Tools."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from schedule.constants import MIN_CANDIDATE_MINUTES, MIN_PEOPLE, SLOT_MINUTES
from schedule.timeutil import ceil_to_slot, day_start_seoul, to_seoul


@dataclass(frozen=True)
class Candidate:
    starts_at: datetime
    ends_at: datetime
    member_ids: frozenset[str]

    @property
    def available_count(self) -> int:
        return len(self.member_ids)

    @property
    def duration(self) -> timedelta:
        return self.ends_at - self.starts_at


def _slot_starts(day: date) -> list[datetime]:
    start = day_start_seoul(day)
    return [start + timedelta(minutes=SLOT_MINUTES * i) for i in range(48)]


def _member_covers(ranges: list[tuple[datetime, datetime]], slot: datetime) -> bool:
    slot_end = slot + timedelta(minutes=SLOT_MINUTES)
    for start, end in ranges:
        if start <= slot and end >= slot_end:
            return True
    return False


def _build_day_sets(
    day: date,
    member_ranges: dict[str, list[tuple[datetime, datetime]]],
    cutoff: datetime,
) -> dict[datetime, frozenset[str]]:
    result: dict[datetime, frozenset[str]] = {}
    for slot in _slot_starts(day):
        if slot < cutoff:
            continue
        present = frozenset(
            mid
            for mid, ranges in member_ranges.items()
            if _member_covers(ranges, slot)
        )
        result[slot] = present
    return result


def _intersection(slots: Iterable[datetime], day_sets: dict[datetime, frozenset[str]]) -> frozenset[str]:
    it = iter(slots)
    try:
        first = next(it)
    except StopIteration:
        return frozenset()
    acc = set(day_sets.get(first, frozenset()))
    for slot in it:
        acc &= day_sets.get(slot, frozenset())
        if len(acc) < MIN_PEOPLE:
            break
    return frozenset(acc)


def _maximal_candidates_for_day(
    day: date,
    day_sets: dict[datetime, frozenset[str]],
) -> list[Candidate]:
    slots = sorted(day_sets.keys())
    if not slots:
        return []
    day_end = day_start_seoul(day) + timedelta(days=1)
    found: list[Candidate] = []

    for i, left in enumerate(slots):
        for j in range(i, len(slots)):
            window = slots[i : j + 1]
            # Contiguous 30-min slots only
            if any(
                slots[k + 1] - slots[k] != timedelta(minutes=SLOT_MINUTES)
                for k in range(i, j)
            ):
                break
            inter = _intersection(window, day_sets)
            if len(inter) < MIN_PEOPLE:
                break
            right = slots[j] + timedelta(minutes=SLOT_MINUTES)
            if (right - left) < timedelta(minutes=MIN_CANDIDATE_MINUTES):
                continue
            # Maximality: cannot extend left/right keeping same I
            can_left = False
            if i > 0 and slots[i] - slots[i - 1] == timedelta(minutes=SLOT_MINUTES):
                left_ext = _intersection([slots[i - 1], *window], day_sets)
                can_left = left_ext == inter
            can_right = False
            if j + 1 < len(slots) and slots[j + 1] - slots[j] == timedelta(
                minutes=SLOT_MINUTES
            ):
                right_ext = _intersection([*window, slots[j + 1]], day_sets)
                can_right = right_ext == inter
            # Also: if right is not day end and next slot missing from day_sets due to cutoff,
            # treated as cannot extend.
            if right < day_end and j + 1 >= len(slots):
                can_right = False
            if can_left or can_right:
                continue
            found.append(Candidate(starts_at=left, ends_at=right, member_ids=inter))

    # Deduplicate identical (L,R,I)
    unique: dict[tuple[datetime, datetime, frozenset[str]], Candidate] = {}
    for c in found:
        unique[(c.starts_at, c.ends_at, c.member_ids)] = c
    return list(unique.values())


def compute_candidates(
    member_ranges: dict[str, list[tuple[datetime, datetime]]],
    *,
    now: datetime,
    scope_starts_at: datetime,
    scope_ends_at: datetime,
    allowed_dates: set[date] | None = None,
) -> list[Candidate]:
    """Return sorted candidates: |I| DESC → duration DESC → start ASC."""
    if len(member_ranges) < MIN_PEOPLE:
        return []

    cutoff = max(ceil_to_slot(now), to_seoul(scope_starts_at))
    scope_end = to_seoul(scope_ends_at)
    if cutoff >= scope_end:
        return []

    # Normalize ranges to Seoul
    normalized: dict[str, list[tuple[datetime, datetime]]] = {}
    for mid, ranges in member_ranges.items():
        normalized[mid] = [(to_seoul(a), to_seoul(b)) for a, b in ranges if b > a]

    days: list[date] = []
    d = cutoff.date()
    end_day = (scope_end - timedelta(microseconds=1)).date()
    while d <= end_day:
        if allowed_dates is None or d in allowed_dates:
            days.append(d)
        d += timedelta(days=1)

    all_candidates: list[Candidate] = []
    for day in days:
        day_sets = _build_day_sets(day, normalized, cutoff)
        # Clip slots to scope_end
        day_sets = {
            slot: members
            for slot, members in day_sets.items()
            if slot < scope_end and slot + timedelta(minutes=SLOT_MINUTES) <= scope_end
            or (slot < scope_end)
        }
        # Keep only slots fully inside scope
        day_sets = {
            slot: members
            for slot, members in day_sets.items()
            if slot >= cutoff and slot + timedelta(minutes=SLOT_MINUTES) <= scope_end
        }
        all_candidates.extend(_maximal_candidates_for_day(day, day_sets))

    all_candidates.sort(
        key=lambda c: (-c.available_count, -c.duration.total_seconds(), c.starts_at)
    )
    return all_candidates


def prepare_voting_candidates(
    candidates: list[Candidate],
    *,
    now: datetime,
) -> tuple[list[Candidate], datetime | None, int]:
    """Apply Q30: drop soon-starting candidates until voting window >= 1h or <2 left.

    Returns (remaining_sorted, voting_ends_at, excluded_count).
    """
    from schedule.constants import MIN_VOTING, VOTE_LEAD, VOTING_DURATION

    remaining = list(candidates)
    excluded = 0
    now_s = to_seoul(now)
    while True:
        if len(remaining) < 2:
            return remaining, None, excluded
        earliest = min(c.starts_at for c in remaining)
        ends = min(now_s + VOTING_DURATION, to_seoul(earliest) - VOTE_LEAD)
        if ends - now_s >= MIN_VOTING:
            remaining.sort(
                key=lambda c: (-c.available_count, -c.duration.total_seconds(), c.starts_at)
            )
            return remaining, ends, excluded
        # Exclude the earliest-starting candidate
        earliest = min(remaining, key=lambda c: c.starts_at)
        remaining = [c for c in remaining if c is not earliest]
        excluded += 1
