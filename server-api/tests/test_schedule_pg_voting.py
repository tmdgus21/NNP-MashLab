"""PostgreSQL 18 integration: Alembic 0005 + voting confirm + concurrent close.

Skipped unless SCHEDULE_PG_URL is set (temporary local PG only; never ops).
"""
from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

PG_URL = os.environ.get(
    "SCHEDULE_PG_URL",
    "",
)


@unittest.skipUnless(PG_URL, "SCHEDULE_PG_URL not set")
class SchedulePostgresVotingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = PG_URL
        os.environ["ADMIN_ENABLED"] = "0"
        from alembic import command
        from alembic.config import Config
        from pathlib import Path
        from sqlalchemy import create_engine, text

        root = Path(__file__).resolve().parents[1]
        eng = create_engine(PG_URL)
        with eng.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE"))
            c.execute(text("CREATE SCHEMA public"))
        eng.dispose()
        cfg = Config(str(root / "alembic.v21.ini"))
        command.upgrade(cfg, "head")

        import database as database_module

        database_module._engine = None

    @classmethod
    def tearDownClass(cls):
        import database as database_module

        database_module._engine = None
        if cls._prev_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = cls._prev_database_url

    def test_vote_confirm_and_concurrent_close(self):
        import secrets

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine, select, text

        import database as database_module
        from database import session
        from db_v21.models.room import Room, RoomMember
        from db_v21.models.schedule import (
            ScheduleCollection,
            ScheduleResult,
            ScheduleRun,
        )
        from schedule import service as svc
        from schedule.constants import SEOUL
        from schedule.router import router as schedule_router
        from schedule.timeutil import ceil_to_slot, seoul_today
        from user_auth import router as auth_router

        database_module._engine = None
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(schedule_router)
        client = TestClient(app)

        from tests.auth_helpers import auth_headers

        def reg(nick_prefix):
            return auth_headers(
                client, email=f"{nick_prefix}-{secrets.token_hex(3)}@example.test"
            )

        h1, h2, h3 = reg("a"), reg("b"), reg("c")
        today = seoul_today()
        created = client.post(
            "/v1/meetings",
            headers=h1,
            json={
                "title": "PG투표",
                "nickname": "A",
                "startDate": today.isoformat(),
                "endDate": (today + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(201, created.status_code, created.text)
        mid = created.json()["id"]
        code = created.json()["code"]
        cid = created.json()["collectionId"]
        client.post("/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"})
        client.post("/v1/meetings/join", headers=h3, json={"code": code, "nickname": "C"})

        now = datetime.now(SEOUL)
        start = ceil_to_slot(now + timedelta(hours=4))
        mid_s = start + timedelta(hours=1)
        mid_e = mid_s + timedelta(hours=1)
        end = start + timedelta(hours=3)

        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            col.scope_starts_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
            col.scope_ends_at = end + timedelta(hours=1)
            members = {
                m.nickname: m
                for m in db.scalars(select(RoomMember).where(RoomMember.room_id == mid))
            }
            svc.submit_response(db, room, members["A"], cid, [(start, end)], now=now)
            svc.submit_response(db, room, members["B"], cid, [(start, end)], now=now)
            svc.submit_response(db, room, members["C"], cid, [(mid_s, mid_e)], now=now)
            col = db.get(ScheduleCollection, cid)
            col.grace_until = now
            svc.close_collection_if_due(db, mid, now=now + timedelta(minutes=1))
            run = db.scalar(
                select(ScheduleRun)
                .where(ScheduleRun.room_id == mid)
                .order_by(ScheduleRun.created_at.desc())
            )
            self.assertEqual("reviewing", db.get(Room, mid).progress_status)
            run.voting_ends_at = now + timedelta(hours=5)

        cands = client.get(f"/v1/meetings/{mid}/candidates", headers=h1).json()[
            "candidates"
        ]
        self.assertGreaterEqual(len(cands), 2)
        # empty ballots from all → early confirm
        for h in (h1, h2, h3):
            r = client.put(
                f"/v1/meetings/{mid}/votes/me",
                headers=h,
                json={"candidateIds": []},
            )
            self.assertEqual(200, r.status_code, r.text)
        self.assertEqual(
            "CONFIRMED",
            client.get(f"/v1/meetings/{mid}", headers=h1).json()["status"],
        )

        # Concurrent idempotent TIMEOUT close on a second VOTING room
        created2 = client.post(
            "/v1/meetings",
            headers=h1,
            json={
                "title": "PG동시",
                "nickname": "A2",
                "startDate": today.isoformat(),
                "endDate": (today + timedelta(days=2)).isoformat(),
            },
        )
        mid2 = created2.json()["id"]
        code2 = created2.json()["code"]
        cid2 = created2.json()["collectionId"]
        client.post(
            "/v1/meetings/join", headers=h2, json={"code": code2, "nickname": "B2"}
        )
        client.post(
            "/v1/meetings/join", headers=h3, json={"code": code2, "nickname": "C2"}
        )
        with session() as db, db.begin():
            room = db.get(Room, mid2)
            col = db.get(ScheduleCollection, cid2)
            col.scope_starts_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
            col.scope_ends_at = end + timedelta(hours=1)
            members = {
                m.nickname: m
                for m in db.scalars(select(RoomMember).where(RoomMember.room_id == mid2))
            }
            svc.submit_response(db, room, members["A2"], cid2, [(start, end)], now=now)
            svc.submit_response(db, room, members["B2"], cid2, [(start, end)], now=now)
            svc.submit_response(
                db, room, members["C2"], cid2, [(mid_s, mid_e)], now=now
            )
            col = db.get(ScheduleCollection, cid2)
            col.grace_until = now
            svc.close_collection_if_due(db, mid2, now=now + timedelta(minutes=1))
            room = db.get(Room, mid2)
            self.assertEqual("reviewing", room.progress_status)
            run = db.scalar(
                select(ScheduleRun)
                .where(ScheduleRun.room_id == mid2)
                .order_by(ScheduleRun.created_at.desc())
            )
            run.voting_ends_at = now - timedelta(seconds=1)

        def closer(_):
            import database as dm

            dm._engine = None
            with session() as db, db.begin():
                return svc.close_voting_if_due(db, mid2, now=datetime.now(SEOUL))

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(closer, range(4)))
        self.assertEqual(1, sum(1 for x in results if x is True), results)
        eng = create_engine(PG_URL)
        with eng.connect() as c:
            n = c.execute(
                text("select count(*) from schedule_results where room_id=:r"),
                {"r": mid2},
            ).scalar()
            self.assertEqual(1, n)
        eng.dispose()


if __name__ == "__main__":
    unittest.main()
