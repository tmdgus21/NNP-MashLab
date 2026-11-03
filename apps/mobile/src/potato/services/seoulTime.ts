/**
 * The server returns instants (PostgreSQL: "2026-11-05T01:00:00Z") but also naive
 * Seoul wall-clock values (SQLite: "2026-11-05T10:00:00"). Both must display as Seoul time.
 */
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];
const HAS_OFFSET = /(Z|[+-]\d{2}:?\d{2})$/;

export interface SeoulMoment {
  date: string;
  minutes: number;
  weekday: string;
}

export function toSeoul(iso: string): SeoulMoment {
  const ms = Date.parse(HAS_OFFSET.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(ms)) {
    throw new Error(`Invalid timestamp: ${iso}`);
  }
  const shifted = new Date(HAS_OFFSET.test(iso) ? ms + 9 * 3600 * 1000 : ms);
  const pad = (value: number) => String(value).padStart(2, '0');
  return {
    date: `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())}`,
    minutes: shifted.getUTCHours() * 60 + shifted.getUTCMinutes(),
    weekday: WEEKDAYS[shifted.getUTCDay()],
  };
}

export function formatClock(minutes: number): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;
}

export function formatDateKo(date: string): string {
  const [, month, day] = date.split('-').map(Number);
  return `${month}월 ${day}일`;
}

/** "11월 5일 (수) 10:00~11:00" */
export function formatSeoulRange(startsAt: string, endsAt: string): string {
  const start = toSeoul(startsAt);
  const end = toSeoul(endsAt);
  const endClock = end.date === start.date ? formatClock(end.minutes) : `${formatDateKo(end.date)} ${formatClock(end.minutes)}`;
  return `${formatDateKo(start.date)} (${start.weekday}) ${formatClock(start.minutes)}~${endClock}`;
}
