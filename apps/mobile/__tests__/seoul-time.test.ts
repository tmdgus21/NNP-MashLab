import { formatSeoulRange, toSeoul } from '../src/potato/services/seoulTime';

test('PostgreSQL instants (Z) are shown in Seoul time', () => {
  expect(formatSeoulRange('2026-11-05T01:00:00Z', '2026-11-05T02:00:00Z')).toBe('11월 5일 (목) 10:00~11:00');
  expect(toSeoul('2026-11-04T15:30:00+00:00')).toMatchObject({ date: '2026-11-05', minutes: 30 }); // crosses midnight
});

test('SQLite naive values are already Seoul wall-clock and must not be shifted', () => {
  expect(formatSeoulRange('2026-11-05T10:00:00', '2026-11-05T11:00:00')).toBe('11월 5일 (목) 10:00~11:00');
});

test('an offset of +09:00 is the same moment as Z', () => {
  expect(toSeoul('2026-11-05T10:00:00+09:00')).toEqual(toSeoul('2026-11-05T01:00:00Z'));
});

test('a range that ends on the next day names the date', () => {
  expect(formatSeoulRange('2026-11-05T14:00:00Z', '2026-11-05T16:00:00Z')).toBe('11월 5일 (목) 23:00~11월 6일 01:00');
});

test('garbage is rejected, never displayed as a time', () => {
  expect(() => toSeoul('not a date')).toThrow();
});
