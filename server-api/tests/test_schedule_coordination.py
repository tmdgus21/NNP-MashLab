"""Pure coordination algorithm tests (T6/T7)."""
from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ADMIN_ENABLED", "0")

from schedule.constants import SEOUL
from schedule.coordination import compute_candidates, prepare_voting_candidates


def _dt(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=SEOUL)


class CoordinationTests(unittest.TestCase):
    def test_t6_2_sixty_minutes_one_candidate(self):
        ranges = {
            "a": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 12))],
            "b": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 12))],
        }
        cands = compute_candidates(
            ranges,
            now=_dt(2026, 11, 20, 9),
            scope_starts_at=_dt(2026, 11, 20, 0),
            scope_ends_at=_dt(2026, 11, 21, 0),
        )
        self.assertEqual(1, len(cands))
        self.assertEqual(_dt(2026, 11, 20, 10), cands[0].starts_at)
        self.assertEqual(_dt(2026, 11, 20, 12), cands[0].ends_at)

    def test_t6_1_thirty_minutes_zero(self):
        ranges = {
            "a": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 10, 30))],
            "b": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 10, 30))],
        }
        cands = compute_candidates(
            ranges,
            now=_dt(2026, 11, 20, 9),
            scope_starts_at=_dt(2026, 11, 20, 0),
            scope_ends_at=_dt(2026, 11, 21, 0),
        )
        self.assertEqual([], cands)

    def test_t6_3_solo_zero(self):
        ranges = {"a": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 13))]}
        cands = compute_candidates(
            ranges,
            now=_dt(2026, 11, 20, 9),
            scope_starts_at=_dt(2026, 11, 20, 0),
            scope_ends_at=_dt(2026, 11, 21, 0),
        )
        self.assertEqual([], cands)

    def test_t6_7_ab_and_abc(self):
        ranges = {
            "a": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 13))],
            "b": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 13))],
            "c": [(_dt(2026, 11, 20, 11), _dt(2026, 11, 20, 12))],
        }
        cands = compute_candidates(
            ranges,
            now=_dt(2026, 11, 20, 9),
            scope_starts_at=_dt(2026, 11, 20, 0),
            scope_ends_at=_dt(2026, 11, 21, 0),
        )
        self.assertEqual(2, len(cands), cands)
        # sort: 3 people first
        self.assertEqual(3, cands[0].available_count)
        self.assertEqual(_dt(2026, 11, 20, 11), cands[0].starts_at)
        self.assertEqual(_dt(2026, 11, 20, 12), cands[0].ends_at)
        self.assertEqual(frozenset({"a", "b", "c"}), cands[0].member_ids)
        self.assertEqual(2, cands[1].available_count)
        self.assertEqual(_dt(2026, 11, 20, 10), cands[1].starts_at)
        self.assertEqual(_dt(2026, 11, 20, 13), cands[1].ends_at)
        self.assertEqual(frozenset({"a", "b"}), cands[1].member_ids)
        # no partial AB segments
        spans = {(c.starts_at, c.ends_at) for c in cands}
        self.assertNotIn((_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 11)), spans)
        self.assertNotIn((_dt(2026, 11, 20, 12), _dt(2026, 11, 20, 13)), spans)

    def test_t6_6_past_cutoff(self):
        ranges = {
            "a": [(_dt(2026, 11, 20, 11), _dt(2026, 11, 20, 12))],
            "b": [(_dt(2026, 11, 20, 11), _dt(2026, 11, 20, 12))],
        }
        cands = compute_candidates(
            ranges,
            now=_dt(2026, 11, 20, 11, 5),
            scope_starts_at=_dt(2026, 11, 20, 0),
            scope_ends_at=_dt(2026, 11, 21, 0),
        )
        # ceil 11:05 → 11:30, only 30m left → 0
        self.assertEqual([], cands)

    def test_t7_1_people_before_duration(self):
        ranges = {
            "a": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 13))],
            "b": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 13))],
            "c": [(_dt(2026, 11, 20, 10), _dt(2026, 11, 20, 11))],
        }
        cands = compute_candidates(
            ranges,
            now=_dt(2026, 11, 20, 9),
            scope_starts_at=_dt(2026, 11, 20, 0),
            scope_ends_at=_dt(2026, 11, 21, 0),
        )
        self.assertGreaterEqual(len(cands), 2)
        self.assertEqual(3, cands[0].available_count)

    def test_prepare_voting_excludes_soon(self):
        from schedule.coordination import Candidate

        cands = [
            Candidate(
                _dt(2026, 11, 20, 12),
                _dt(2026, 11, 20, 14),
                frozenset({"a", "b"}),
            ),
            Candidate(
                _dt(2026, 11, 20, 18),
                _dt(2026, 11, 20, 20),
                frozenset({"a", "b"}),
            ),
        ]
        remaining, ends, excluded = prepare_voting_candidates(
            cands, now=_dt(2026, 11, 20, 11, 45)
        )
        # 12:00 - 30m = 11:30 already past relative to 11:45 → exclude first
        self.assertGreaterEqual(excluded, 1)
        self.assertTrue(all(c.starts_at >= _dt(2026, 11, 20, 18) for c in remaining) or len(remaining) <= 1)


if __name__ == "__main__":
    unittest.main()
