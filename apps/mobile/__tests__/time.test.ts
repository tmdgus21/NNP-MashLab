import {
  covers,
  intervalsToSlots,
  normalizeIntervals,
  overlaps,
  paintSlots,
  parseTime,
  slotsToIntervals,
  timeLabel,
  validDate,
} from '../src/domain/time';
const date = '2026-10-17';
test('merges adjacent slots, preserves gaps and midnight boundary', () => {
  expect(slotsToIntervals(date, [22, 20, 21, 20, 47])).toEqual([
    { date, start: 600, end: 690 },
    { date, start: 1410, end: 1440 },
  ]);
  expect(timeLabel(1440)).toBe('24:00');
  expect(parseTime('09:30')).toBe(570);
});
test('round trip remains lossless for varied selections', () => {
  for (let seed = 0; seed < 100; seed++) {
    const slots = Array.from({ length: 48 }, (_, s) => s).filter(
      s => (s * 17 + seed * 7) % 11 < 5,
    );
    expect(intervalsToSlots(slotsToIntervals(date, slots), date)).toEqual(
      slots,
    );
  }
});
test('fast/reverse drags interpolate every cell and erase without holes', () => {
  expect(paintSlots([], 8, 3, false)).toEqual([3, 4, 5, 6, 7, 8]);
  expect(paintSlots([3, 4, 5, 6, 7, 8], 4, 7, true)).toEqual([3, 8]);
  expect(paintSlots([], -2, 1, false)).toEqual([0, 1]);
  expect(paintSlots([], 46, 50, false)).toEqual([46, 47]);
});
test('validates dates, half-hour boundaries and zero/negative ranges', () => {
  expect(validDate('2026-02-30')).toBe(false);
  expect(() => slotsToIntervals(date, [48])).toThrow();
  expect(() => parseTime('25:00')).toThrow();
  expect(() => parseTime('12:15')).toThrow();
  expect(() =>
    intervalsToSlots([{ date, start: 600, end: 600 }], date),
  ).toThrow();
});
test('half-open overlap and merged coverage work across multiple days', () => {
  const a = { date, start: 600, end: 630 };
  const b = { date, start: 630, end: 660 };
  expect(overlaps(a, b)).toBe(false);
  expect(covers([a, b], { date, start: 600, end: 660 })).toBe(true);
  expect(covers([a], { ...a, date: '2026-10-18' })).toBe(false);
  expect(normalizeIntervals([b, a, a])).toEqual([
    { date, start: 600, end: 660 },
  ]);
});
