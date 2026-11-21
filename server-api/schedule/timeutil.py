"""Asia/Seoul wall-clock helpers and 30-minute slot alignment."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone

from schedule.constants import SEOUL, SLOT_MINUTES


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # SQLite strips tzinfo; Potato Meet stores Asia/Seoul wall clocks.
        return dt.replace(tzinfo=SEOUL).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def to_seoul(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SEOUL)
    return dt.astimezone(SEOUL)


def seoul_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(SEOUL)
    return to_seoul(now)


def seoul_today(now: datetime | None = None) -> date:
    return seoul_now(now).date()


def day_start_seoul(d: date) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=SEOUL)


def add_calendar_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def room_bounds_from_dates(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """rooms.starts_at = start 00:00 KST; ends_at = day after end 00:00 KST."""
    starts = day_start_seoul(start_date)
    ends = day_start_seoul(end_date + timedelta(days=1))
    return starts, ends


def validate_meeting_dates(start_date: date, end_date: date, now: datetime | None = None) -> None:
    today = seoul_today(now)
    if start_date < today:
        raise ValueError("시작일은 오늘 이후여야 합니다.")
    if end_date < start_date:
        raise ValueError("종료일은 시작일 이후여야 합니다.")
    max_end = add_calendar_months(today, 1)
    if end_date > max_end:
        raise ValueError("종료일은 오늘부터 1개월 이내여야 합니다.")


def validate_selected_dates(
    dates: list[date], now: datetime | None = None
) -> list[date]:
    """Normalize selected calendar days (unique, sorted). At least one day."""
    today = seoul_today(now)
    max_end = add_calendar_months(today, 1)
    if not dates:
        raise ValueError("날짜를 1개 이상 선택해 주세요.")
    uniq = sorted(set(dates))
    for day in uniq:
        if day < today:
            raise ValueError("과거 날짜는 선택할 수 없습니다.")
        if day > max_end:
            raise ValueError("날짜는 오늘부터 1개월 이내여야 합니다.")
    return uniq


def expand_dates_in_bounds(starts_at: datetime, ends_at: datetime) -> list[date]:
    """Inclusive calendar days covered by [starts_at, ends_at) in Seoul."""
    start = to_seoul(starts_at).date()
    end_exclusive = to_seoul(ends_at)
    last = (end_exclusive - timedelta(microseconds=1)).date()
    if last < start:
        return []
    out: list[date] = []
    day = start
    while day <= last:
        out.append(day)
        day += timedelta(days=1)
    return out


def selected_dates_for_room(
    meeting_settings: dict | None,
    starts_at: datetime,
    ends_at: datetime,
) -> list[date]:
    """Explicit selectedDates, or legacy continuous expansion of room bounds."""
    settings = meeting_settings or {}
    raw = settings.get("selectedDates")
    if raw is None:
        raw = settings.get("selected_dates")
    if isinstance(raw, list) and raw:
        parsed: list[date] = []
        for item in raw:
            if isinstance(item, date) and not isinstance(item, datetime):
                parsed.append(item)
            else:
                parsed.append(date.fromisoformat(str(item)[:10]))
        return sorted(set(parsed))
    return expand_dates_in_bounds(starts_at, ends_at)


def is_slot_aligned(dt: datetime) -> bool:
    local = to_seoul(dt)
    return local.second == 0 and local.microsecond == 0 and local.minute % SLOT_MINUTES == 0


def ceil_to_slot(dt: datetime) -> datetime:
    """Smallest Seoul 30-minute boundary >= dt."""
    local = to_seoul(dt)
    floored = local.replace(second=0, microsecond=0) - timedelta(
        minutes=local.minute % SLOT_MINUTES
    )
    if floored < local:
        return floored + timedelta(minutes=SLOT_MINUTES)
    return floored


def parse_iso_dt(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("시간대(+09:00)가 필요합니다.")
    return to_seoul(dt)


def format_iso(dt: datetime) -> str:
    return to_seoul(dt).isoformat()
