"""selectedDates create / submit / coordinate filters."""
from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import initialize
from schedule import ai_summary as summary_mod
from schedule.constants import SEOUL
from schedule.coordination import compute_candidates
from schedule.router import router as schedule_router
from schedule.timeutil import day_start_seoul, selected_dates_for_room
from tests.auth_helpers import auth_headers, set_nickname
from user_auth import router as auth_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(schedule_router)
    return app


class SelectedDatesTests(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        summary_mod._background_enabled = False
        self.client = TestClient(_app())
        self.fixed = datetime(2026, 11, 20, 9, 0, tzinfo=SEOUL)

    def tearDown(self):
        summary_mod._background_enabled = True
        self.client.close()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    @contextmanager
    def _frozen_clock(self):
        with (
            patch("schedule.service.utc_now", return_value=self.fixed),
            patch("schedule.service.seoul_now", return_value=self.fixed),
            patch("schedule.timeutil.seoul_today", return_value=self.fixed.date()),
        ):
            yield

    def _create(self, headers, body):
        with self._frozen_clock():
            return self.client.post("/v1/meetings", headers=headers, json=body)

    def _put_response(self, mid, cid, headers, body):
        with self._frozen_clock():
            return self.client.put(
                f"/v1/meetings/{mid}/collections/{cid}/response",
                headers=headers,
                json=body,
            )

    def _join(self, headers, code, nick):
        with self._frozen_clock():
            return self.client.post(
                "/v1/meetings/join",
                headers=headers,
                json={"code": code, "nickname": nick},
            )

    def test_selected_dates_create_and_legacy_expand(self):
        h = auth_headers(self.client)
        set_nickname(self.client, h, "방장")
        res = self._create(
            h,
            {
                "title": "복수날짜",
                "nickname": "방장",
                "selectedDates": ["2026-11-20", "2026-11-26", "2026-11-30"],
            },
        )
        self.assertEqual(201, res.status_code, res.text)
        body = res.json()
        self.assertEqual(
            body["selectedDates"], ["2026-11-20", "2026-11-26", "2026-11-30"]
        )
        self.assertTrue(body["startsAt"].startswith("2026-11-20"))
        # endsAt is day after last selected (exclusive)
        self.assertTrue(body["endsAt"].startswith("2026-12-01"))

        both = self._create(
            h,
            {
                "title": "충돌",
                "nickname": "방장",
                "selectedDates": ["2026-11-21"],
                "startDate": "2026-11-21",
                "endDate": "2026-11-22",
            },
        )
        self.assertEqual(422, both.status_code, both.text)

        legacy = self._create(
            h,
            {
                "title": "범위",
                "nickname": "방장2",
                "startDate": "2026-11-20",
                "endDate": "2026-11-22",
            },
        )
        self.assertEqual(201, legacy.status_code, legacy.text)
        self.assertEqual(
            legacy.json()["selectedDates"],
            ["2026-11-20", "2026-11-21", "2026-11-22"],
        )

    def test_reject_gap_day_submit_and_coordinate_skips_gap(self):
        h1 = auth_headers(self.client)
        h2 = auth_headers(self.client)
        set_nickname(self.client, h1, "A")
        set_nickname(self.client, h2, "B")
        created = self._create(
            h1,
            {
                "title": "갭",
                "nickname": "A",
                "selectedDates": ["2026-11-20", "2026-11-26", "2026-11-30"],
            },
        )
        self.assertEqual(201, created.status_code, created.text)
        mid = created.json()["id"]
        code = created.json()["code"]
        cid = created.json()["collectionId"]
        self.assertEqual(201, self._join(h2, code, "B").status_code)

        # Gap day 2026-11-21 must be rejected (clock frozen so collection stays OPEN)
        gap = self._put_response(
            mid,
            cid,
            h1,
            {
                "available": [
                    {
                        "start": "2026-11-21T10:00:00+09:00",
                        "end": "2026-11-21T12:00:00+09:00",
                    }
                ]
            },
        )
        self.assertEqual(422, gap.status_code, gap.text)

        # Selected day OK
        ok = self._put_response(
            mid,
            cid,
            h1,
            {
                "available": [
                    {
                        "start": "2026-11-26T10:00:00+09:00",
                        "end": "2026-11-26T12:00:00+09:00",
                    }
                ]
            },
        )
        self.assertEqual(200, ok.status_code, ok.text)

        # Coordination must not invent candidates on gap days
        mid_a = "m1"
        mid_b = "m2"
        day_gap = date(2026, 11, 21)
        day_ok = date(2026, 11, 26)
        ranges = {
            mid_a: [
                (day_start_seoul(day_gap) + timedelta(hours=10), day_start_seoul(day_gap) + timedelta(hours=12)),
                (day_start_seoul(day_ok) + timedelta(hours=10), day_start_seoul(day_ok) + timedelta(hours=12)),
            ],
            mid_b: [
                (day_start_seoul(day_gap) + timedelta(hours=10), day_start_seoul(day_gap) + timedelta(hours=12)),
                (day_start_seoul(day_ok) + timedelta(hours=10), day_start_seoul(day_ok) + timedelta(hours=12)),
            ],
        }
        now = datetime(2026, 11, 20, 9, 0, tzinfo=SEOUL)
        cands = compute_candidates(
            ranges,
            now=now,
            scope_starts_at=day_start_seoul(date(2026, 11, 20)),
            scope_ends_at=day_start_seoul(date(2026, 12, 1)),
            allowed_dates={date(2026, 11, 20), date(2026, 11, 26), date(2026, 11, 30)},
        )
        self.assertTrue(cands)
        self.assertTrue(all(c.starts_at.date() != day_gap for c in cands))
        self.assertTrue(any(c.starts_at.date() == day_ok for c in cands))

    def test_legacy_settings_expand(self):
        starts = day_start_seoul(date(2026, 11, 20))
        ends = day_start_seoul(date(2026, 11, 23))
        self.assertEqual(
            selected_dates_for_room(
                {"startDate": "2026-11-20", "endDate": "2026-11-22"},
                starts,
                ends,
            ),
            [date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 22)],
        )


if __name__ == "__main__":
    unittest.main()
