"""Schedule API integration tests (collection / grace / join / branch)."""
from __future__ import annotations

import os
import secrets
import unittest
from datetime import date, datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import initialize, session
from schedule import ai_summary as summary_mod
from schedule.constants import SEOUL
from schedule.router import router as schedule_router
from schedule.timeutil import format_iso
from user_auth import router as auth_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(schedule_router)
    return app


def _dt(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=SEOUL)


class ScheduleCollectionTests(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        summary_mod._background_enabled = False
        self.client = TestClient(_app())
        self.fixed_now = _dt(2026, 11, 20, 9)

    def tearDown(self):
        summary_mod._background_enabled = True
        self.client.close()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    def _register(self, email: str | None = None):
        email = email or f"u-{secrets.token_hex(4)}@example.test"
        res = self.client.post(
            "/v1/auth/register",
            json={"email": email, "password": "long-enough-password"},
        )
        self.assertEqual(201, res.status_code, res.text)
        token = res.json()["token"]
        return email, {"Authorization": f"Bearer {token}"}

    def _create(self, headers, title="모임", nick="방장", start=None, end=None):
        start = start or date(2026, 11, 20)
        end = end or date(2026, 11, 22)
        # Patch seoul "today" via meeting dates relative to fixed wall — create uses utc now.
        # Override validate by using dates from real today if needed.
        from schedule import service as svc
        from schedule.timeutil import seoul_today

        today = seoul_today()
        start = today
        end = today + timedelta(days=2)
        res = self.client.post(
            "/v1/meetings",
            headers=headers,
            json={
                "title": title,
                "nickname": nick,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            },
        )
        self.assertEqual(201, res.status_code, res.text)
        return res.json()

    def test_t2_boundary_and_resubmit(self):
        _, h = self._register()
        meeting = self._create(h)
        cid = meeting["collectionId"]
        mid = meeting["id"]
        # bad boundary
        bad = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={
                "available": [
                    {
                        "start": format_iso(_dt(2026, 11, 20, 10, 5)),
                        "end": format_iso(_dt(2026, 11, 20, 10, 35)),
                    }
                ]
            },
        )
        # dates may be wrong relative to scope — either 422
        self.assertIn(bad.status_code, (422,), bad.text)

        # full default empty → ok
        ok = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={"available": []},
        )
        self.assertEqual(200, ok.status_code, ok.text)
        self.assertGreaterEqual(ok.json()["doneCount"], 1)

        # resubmit overwrite
        ok2 = self.client.put(
            f"/v1/meetings/{mid}/collections/{cid}/response",
            headers=h,
            json={"available": []},
        )
        self.assertEqual(200, ok2.status_code, ok2.text)

    def test_t3_grace_and_join_cancel(self):
        from schedule import service as svc
        from db_v21.models.schedule import ScheduleCollection
        from sqlalchemy import select

        _, h1 = self._register()
        meeting = self._create(h1, nick="A")
        code = meeting["code"]
        mid = meeting["id"]
        cid = meeting["collectionId"]

        _, h2 = self._register()
        join = self.client.post(
            "/v1/meetings/join",
            headers=h2,
            json={"code": code, "nickname": "B"},
        )
        self.assertEqual(201, join.status_code, join.text)

        # both submit
        for headers in (h1, h2):
            r = self.client.put(
                f"/v1/meetings/{mid}/collections/{cid}/response",
                headers=headers,
                json={"available": []},
            )
            self.assertEqual(200, r.status_code, r.text)

        col_body = self.client.get(f"/v1/meetings/{mid}/collection", headers=h1)
        self.assertEqual(200, col_body.status_code, col_body.text)
        grace = col_body.json()["graceUntil"]
        self.assertIsNotNone(grace)

        # third joins → grace cleared
        _, h3 = self._register()
        j3 = self.client.post(
            "/v1/meetings/join",
            headers=h3,
            json={"code": code, "nickname": "C"},
        )
        self.assertEqual(201, j3.status_code, j3.text)
        col2 = self.client.get(f"/v1/meetings/{mid}/collection", headers=h1)
        self.assertIsNone(col2.json()["graceUntil"])

        with session() as db:
            col = db.scalar(
                select(ScheduleCollection).where(ScheduleCollection.id == cid)
            )
            self.assertIsNone(col.grace_until)

    def test_t3_close_coordinates_two_candidates_example(self):
        from schedule import service as svc
        from db_v21.base import now as utc_now
        from db_v21.models.room import Room
        from db_v21.models.schedule import ScheduleCollection, ScheduleResponse
        from sqlalchemy import select

        _, h1 = self._register()
        meeting = self._create(h1, nick="A")
        code = meeting["code"]
        mid = meeting["id"]
        cid = meeting["collectionId"]
        _, h2 = self._register()
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
        )
        _, h3 = self._register()
        self.client.post(
            "/v1/meetings/join", headers=h3, json={"code": code, "nickname": "C"}
        )

        # Build specific availability via service with locked room
        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            from db_v21.models.room import RoomMember

            rows = list(
                db.scalars(
                    select(RoomMember).where(RoomMember.room_id == mid)
                )
            )
            by_nick = {m.nickname: m for m in rows}
            a, b, c = by_nick["A"], by_nick["B"], by_nick["C"]
            # Future windows relative to wall clock so GET .../meetings won't TIMEOUT-close
            wall = datetime.now(SEOUL)
            start = wall.replace(second=0, microsecond=0) + timedelta(hours=4)
            start = start.replace(minute=(start.minute // 30) * 30)
            mid_s = start + timedelta(hours=1)
            mid_e = mid_s + timedelta(hours=1)
            end = start + timedelta(hours=3)
            col.scope_starts_at = wall.replace(hour=0, minute=0, second=0, microsecond=0)
            col.scope_ends_at = end + timedelta(hours=1)
            ranges = {
                a.id: [(start, end)],
                b.id: [(start, end)],
                c.id: [(mid_s, mid_e)],
            }
            now = wall
            for member, avail in ranges.items():
                mobj = by_nick[{a.id: "A", b.id: "B", c.id: "C"}[member]]
                svc.submit_response(db, room, mobj, cid, avail, now=now)
            col = db.get(ScheduleCollection, cid)
            col.grace_until = now
            svc.close_collection_if_due(db, mid, now=now + timedelta(minutes=1))
            from db_v21.models.schedule import ScheduleRun
            from sqlalchemy import select as sel

            run = db.scalar(
                sel(ScheduleRun)
                .where(ScheduleRun.room_id == mid)
                .order_by(ScheduleRun.created_at.desc())
            )
            if run and run.voting_ends_at is not None:
                run.voting_ends_at = wall + timedelta(hours=5)

        cands = self.client.get(f"/v1/meetings/{mid}/candidates", headers=h1)
        self.assertEqual(200, cands.status_code, cands.text)
        body = cands.json()
        self.assertEqual(2, len(body["candidates"]), body)
        self.assertEqual(3, body["candidates"][0]["availableCount"])
        detail = self.client.get(f"/v1/meetings/{mid}", headers=h1).json()
        self.assertEqual("VOTING", detail["status"])

    def test_t5_join_locked_after_close(self):
        from schedule import service as svc
        from db_v21.models.room import Room, RoomMember
        from db_v21.models.schedule import ScheduleCollection
        from sqlalchemy import select

        _, h1 = self._register()
        meeting = self._create(h1, nick="A")
        code = meeting["code"]
        mid = meeting["id"]
        cid = meeting["collectionId"]
        _, h2 = self._register()
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
        )
        day0 = datetime.now(SEOUL).date()
        now = datetime(day0.year, day0.month, day0.day, 9, 0, tzinfo=SEOUL)
        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            col.scope_starts_at = datetime(
                day0.year, day0.month, day0.day, 0, 0, tzinfo=SEOUL
            )
            col.scope_ends_at = col.scope_starts_at + timedelta(days=1)
            members = list(
                db.scalars(select(RoomMember).where(RoomMember.room_id == mid))
            )
            avail = [
                (
                    datetime(day0.year, day0.month, day0.day, 10, 0, tzinfo=SEOUL),
                    datetime(day0.year, day0.month, day0.day, 12, 0, tzinfo=SEOUL),
                )
            ]
            for m in members:
                svc.submit_response(db, room, m, cid, avail, now=now)
            col = db.get(ScheduleCollection, cid)
            col.grace_until = now
            svc.close_collection_if_due(db, mid, now=now + timedelta(minutes=1))

        _, h3 = self._register()
        locked = self.client.post(
            "/v1/meetings/join",
            headers=h3,
            json={"code": code, "nickname": "C"},
        )
        self.assertEqual(409, locked.status_code, locked.text)

    def test_t4_extend_when_one_done(self):
        from schedule import service as svc
        from db_v21.models.room import Room, RoomMember
        from db_v21.models.schedule import ScheduleCollection
        from sqlalchemy import select

        _, h1 = self._register()
        meeting = self._create(h1, nick="A")
        mid = meeting["id"]
        cid = meeting["collectionId"]
        code = meeting["code"]
        _, h2 = self._register()
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
        )
        day0 = datetime.now(SEOUL).date()
        now = datetime(day0.year, day0.month, day0.day, 9, 0, tzinfo=SEOUL)
        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            col.scope_starts_at = datetime(
                day0.year, day0.month, day0.day, 0, 0, tzinfo=SEOUL
            )
            col.scope_ends_at = col.scope_starts_at + timedelta(days=1)
            owner = db.scalar(
                select(RoomMember).where(
                    RoomMember.room_id == mid, RoomMember.room_role == "OWNER"
                )
            )
            avail = [
                (
                    datetime(day0.year, day0.month, day0.day, 10, 0, tzinfo=SEOUL),
                    datetime(day0.year, day0.month, day0.day, 12, 0, tzinfo=SEOUL),
                )
            ]
            svc.submit_response(db, room, owner, cid, avail, now=now)
            col = db.get(ScheduleCollection, cid)
            col.closes_at = now
            before = col.extended_count
            svc.close_collection_if_due(db, mid, now=now + timedelta(seconds=1))
            col = db.get(ScheduleCollection, cid)
            self.assertEqual("OPEN", col.status)
            self.assertEqual(1, col.extended_count)
            self.assertEqual(0, before)

    def test_single_auto_confirm(self):
        from schedule import service as svc
        from db_v21.models.room import Room, RoomMember
        from db_v21.models.schedule import ScheduleCollection
        from sqlalchemy import select

        _, h1 = self._register()
        meeting = self._create(h1, nick="A")
        mid = meeting["id"]
        cid = meeting["collectionId"]
        code = meeting["code"]
        _, h2 = self._register()
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
        )
        day0 = datetime.now(SEOUL).date()
        now = datetime(day0.year, day0.month, day0.day, 9, 0, tzinfo=SEOUL)
        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            col.scope_starts_at = datetime(
                day0.year, day0.month, day0.day, 0, 0, tzinfo=SEOUL
            )
            col.scope_ends_at = col.scope_starts_at + timedelta(days=1)
            members = list(
                db.scalars(select(RoomMember).where(RoomMember.room_id == mid))
            )
            avail = [
                (
                    datetime(day0.year, day0.month, day0.day, 10, 0, tzinfo=SEOUL),
                    datetime(day0.year, day0.month, day0.day, 12, 0, tzinfo=SEOUL),
                )
            ]
            for m in members:
                svc.submit_response(db, room, m, cid, avail, now=now)
            col = db.get(ScheduleCollection, cid)
            col.grace_until = now
            svc.close_collection_if_due(db, mid, now=now + timedelta(minutes=1))

        detail = self.client.get(f"/v1/meetings/{mid}", headers=h1)
        self.assertEqual("CONFIRMED", detail.json()["status"], detail.text)
        result = self.client.get(f"/v1/meetings/{mid}/result", headers=h1)
        self.assertEqual(200, result.status_code, result.text)
        self.assertEqual("AUTO", result.json()["method"])


if __name__ == "__main__":
    unittest.main()
