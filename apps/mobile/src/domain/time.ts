import { Interval, intervalSchema } from './model';

export const timeLabel = (minute: number) =>
  `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(
    minute % 60,
  ).padStart(2, '0')}`;
export function parseTime(value: string): number {
  if (!/^(?:[01]\d|2[0-3]):(?:00|30)$/.test(value) && value !== '24:00') {
    throw new Error('시간은 HH:00 또는 HH:30 형식으로 입력하세요.');
  }
  const [h, m] = value.split(':').map(Number);
  return h * 60 + m;
}
export function validDate(value: string) {
  return (
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(value)) &&
    new Date(value).toISOString().slice(0, 10) === value
  );
}
export function slotsToIntervals(date: string, slots: number[]): Interval[] {
  if (
    !validDate(date) ||
    slots.some(s => !Number.isInteger(s) || s < 0 || s > 47)
  ) {
    throw new Error('유효하지 않은 날짜 또는 시간 칸입니다.');
  }
  const sorted = [...new Set(slots)].sort((a, b) => a - b);
  const result: Interval[] = [];
  for (const slot of sorted) {
    const last = result[result.length - 1];
    if (last && last.end === slot * 30) {
      last.end += 30;
    } else {
      result.push({ date, start: slot * 30, end: (slot + 1) * 30 });
    }
  }
  return result;
}
export function intervalsToSlots(
  intervals: Interval[],
  date: string,
): number[] {
  const slots = new Set<number>();
  intervals
    .filter(i => i.date === date)
    .forEach(i => {
      intervalSchema.parse(i);
      for (let s = i.start / 30; s < i.end / 30; s++) {
        slots.add(s);
      }
    });
  return [...slots].sort((a, b) => a - b);
}
export function normalizeIntervals(intervals: Interval[]) {
  return [...new Set(intervals.map(i => i.date))]
    .sort()
    .flatMap(d => slotsToIntervals(d, intervalsToSlots(intervals, d)));
}
export function paintSlots(
  slots: number[],
  from: number,
  to: number,
  erase: boolean,
): number[] {
  const next = new Set(slots);
  for (
    let s = Math.max(0, Math.min(from, to));
    s <= Math.min(47, Math.max(from, to));
    s++
  ) {
    if (erase) {
      next.delete(s);
    } else {
      next.add(s);
    }
  }
  return [...next].sort((a, b) => a - b);
}
export const overlaps = (a: Interval, b: Interval) =>
  a.date === b.date && a.start < b.end && b.start < a.end;
export const covers = (available: Interval[], target: Interval) =>
  normalizeIntervals(available).some(
    i =>
      i.date === target.date && i.start <= target.start && i.end >= target.end,
  );
export const intervalLabel = (i: Interval) =>
  `${i.date.slice(5).replace('-', '/')} ${timeLabel(i.start)}–${timeLabel(
    i.end,
  )}`;
