"""allUnavailable flag vs legacy empty-available semantics."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

import database as database_module

database_module._engine = None
from database import initialize
from schedule.router import router as schedule_router
from schedule.timeutil import format_iso, seoul_today
from tests.auth_helpers import auth_headers, set_nickname
from user_auth import router as auth_router

SEOUL = ZoneInfo("Asia/Seoul")


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(schedule_router)
    return app


class AllUnavailableTests(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        os.environ["ADMIN_ENABLED"] = "0"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        self.client = TestClient(_app())

    def tearDown(self):
        self.client.close()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    def _create(self, headers, dates=None):
        today = seoul_today()
        dates = dates or [today.isoformat(), (today + timedelta(days=2)).isoformat()]
        set_nickname(self.client, headers, "방장")
        res = self.client.post(
            "/v1/meetings",
            headers=headers,
            json={"title": "전체불가능", "selectedDates": dates},
        )
        self.assertEqual(201, res.status_code, res.text)
        return res.json()

    def test_legacy_empty_means_full_available(self):
        h = auth_headers(self.client)
        meeting = self._create(h)
        mid, cid = meeting["id"], meeting["collectionId"]
        ok = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={"available": []},
        )
        self.assertEqual(200, ok.status_code, ok.text)
        body = ok.json()
        self.assertTrue(body["mySubmitted"])
        self.assertGreater(len(body["myAvailable"]), 0)

    def test_all_unavailable_empty_ranges(self):
        h = auth_headers(self.client)
        meeting = self._create(h)
        mid, cid = meeting["id"], meeting["collectionId"]
        ok = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={"available": [], "allUnavailable": True},
        )
        self.assertEqual(200, ok.status_code, ok.text)
        body = ok.json()
        self.assertTrue(body["mySubmitted"])
        self.assertEqual(body["myAvailable"], [])

        again = self.client.get(f"/v1/meetings/{mid}/collection", headers=h)
        self.assertEqual(200, again.status_code, again.text)
        self.assertTrue(again.json()["mySubmitted"])
        self.assertEqual(again.json()["myAvailable"], [])

    def test_all_unavailable_with_ranges_422(self):
        h = auth_headers(self.client)
        meeting = self._create(h)
        mid, cid = meeting["id"], meeting["collectionId"]
        today = seoul_today()
        start = datetime(
            today.year, today.month, today.day, 10, 0, tzinfo=SEOUL
        )
        end = start + timedelta(hours=1)
        bad = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={
                "allUnavailable": True,
                "available": [
                    {"start": format_iso(start), "end": format_iso(end)},
                ],
            },
        )
        self.assertEqual(422, bad.status_code, bad.text)

    def test_not_submitted_vs_all_unavailable(self):
        h = auth_headers(self.client)
        meeting = self._create(h)
        mid = meeting["id"]
        col = self.client.get(f"/v1/meetings/{mid}/collection", headers=h).json()
        self.assertFalse(col["mySubmitted"])
        self.assertEqual(col["myAvailable"], [])

    def test_midnight_boundary_and_gap_day_rejected(self):
        h = auth_headers(self.client)
        today = seoul_today()
        # Use future days so 00:00 is still inside open collection scope.
        d0 = today + timedelta(days=3)
        d2 = today + timedelta(days=5)
        gap = today + timedelta(days=4)
        meeting = self._create(h, dates=[d0.isoformat(), d2.isoformat()])
        mid, cid = meeting["id"], meeting["collectionId"]

        midnight = datetime(d0.year, d0.month, d0.day, 0, 0, tzinfo=SEOUL)
        late = datetime(d0.year, d0.month, d0.day, 23, 30, tzinfo=SEOUL)
        next_mid = midnight + timedelta(days=1)
        ok = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={
                "available": [
                    {"start": format_iso(midnight), "end": format_iso(midnight + timedelta(minutes=30))},
                    {"start": format_iso(late), "end": format_iso(next_mid)},
                ]
            },
        )
        self.assertEqual(200, ok.status_code, ok.text)

        gap_start = datetime(gap.year, gap.month, gap.day, 10, 0, tzinfo=SEOUL)
        rejected = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={
                "available": [
                    {
                        "start": format_iso(gap_start),
                        "end": format_iso(gap_start + timedelta(hours=1)),
                    }
                ]
            },
        )
        self.assertEqual(422, rejected.status_code, rejected.text)

    def test_alternating_month_under_limit(self):
        """Many alternating 30-min cells stay under available max_length=1000."""
        h = auth_headers(self.client)
        today = seoul_today()
        # Start tomorrow so past-slot scope clipping does not reject early hours.
        dates = [(today + timedelta(days=i + 1)).isoformat() for i in range(10)]
        meeting = self._create(h, dates=dates)
        mid, cid = meeting["id"], meeting["collectionId"]
        ranges = []
        for iso in dates:
            d = date.fromisoformat(iso)
            for hour in range(24):
                start = datetime(d.year, d.month, d.day, hour, 0, tzinfo=SEOUL)
                end = start + timedelta(minutes=30)
                ranges.append({"start": format_iso(start), "end": format_iso(end)})
        self.assertLessEqual(len(ranges), 1000)
        ok = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={"available": ranges},
        )
        self.assertEqual(200, ok.status_code, ok.text)
        self.assertTrue(ok.json()["mySubmitted"])
        self.assertGreater(len(ok.json()["myAvailable"]), 0)


if __name__ == "__main__":
    unittest.main()
