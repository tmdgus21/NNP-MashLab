"""Past selectedDates must not reject future availability in the same PUT."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from schedule.collection import validate_available_ranges
from schedule.timeutil import day_start_seoul


KST = timezone(timedelta(hours=9))


class PastDatesSubmitTests(unittest.TestCase):
    def test_validate_clips_past_prefix_keeps_future(self):
        past = date(2026, 11, 20)
        future = date(2026, 11, 25)
        now = datetime(2026, 11, 23, 15, 0, tzinfo=KST)
        scope_start = now  # collection already clipped
        scope_end = day_start_seoul(date(2026, 11, 26))
        allowed = {past, future}

        # Client noise: full past day + future complement of 10:00-11:00 unavailable
        ranges = [
            (day_start_seoul(past), day_start_seoul(past) + timedelta(days=1)),
            (day_start_seoul(future), day_start_seoul(future) + timedelta(hours=10)),
            (
                day_start_seoul(future) + timedelta(hours=11),
                day_start_seoul(future) + timedelta(days=1),
            ),
        ]
        out = validate_available_ranges(
            ranges,
            scope_starts_at=scope_start,
            scope_ends_at=scope_end,
            allowed_dates=allowed,
            now=now,
        )
        self.assertEqual(2, len(out))
        self.assertTrue(all(s.date() == future for s, _ in out))
        self.assertEqual(day_start_seoul(future) + timedelta(hours=10), out[0][1])
        self.assertEqual(day_start_seoul(future) + timedelta(hours=11), out[1][0])

    def test_validate_still_rejects_future_gap_day(self):
        """Non-selected future calendar days still 422 (not silently clipped)."""
        now = datetime(2026, 11, 23, 15, 0, tzinfo=KST)
        gap = date(2026, 11, 27)  # between selected 26 and 30, still in the future
        with self.assertRaises(ValueError):
            validate_available_ranges(
                [
                    (
                        day_start_seoul(gap) + timedelta(hours=10),
                        day_start_seoul(gap) + timedelta(hours=12),
                    )
                ],
                scope_starts_at=now,
                scope_ends_at=day_start_seoul(date(2026, 12, 1)),
                allowed_dates={date(2026, 11, 26), date(2026, 11, 30)},
                now=now,
            )


if __name__ == "__main__":
    unittest.main()
