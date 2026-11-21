"""Full Potato Meet schedule integration on a dedicated PostgreSQL 18 DB.

Requires SCHEDULE_PG_URL (temporary local container only — never ops).
Applies Alembic v21 through 0005, then exercises create→grace sweep→candidates
aiSummary field → concurrent sweep.
"""
from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

PG_URL = os.environ.get("SCHEDULE_PG_URL", "")


@unittest.skipUnless(PG_URL, "SCHEDULE_PG_URL not set")
class SchedulePostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = PG_URL
        os.environ["ADMIN_ENABLED"] = "0"
        from pathlib import Path

        from alembic import command
        from alembic.config import Config
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

    def test_end_to_end_sweep_and_candidates_summary_slot(self):
        import secrets

        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy import select

        import database as database_module
        from database import session
        from db_v21.models.room import Room, RoomMember
        from db_v21.models.schedule import ScheduleCollection, ScheduleRun
        from schedule import ai_summary as summary_mod
        from schedule import service as svc
        from schedule.constants import SEOUL
        from schedule.router import router as schedule_router
        from schedule.timeutil import ceil_to_slot, seoul_today
        from user_auth import router as auth_router

        database_module._engine = None
        summary_mod._background_enabled = False
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(schedule_router)
        client = TestClient(app)

        from tests.auth_helpers import auth_headers, set_nickname

        def reg(prefix):
            return auth_headers(
                client, email=f"{prefix}-{secrets.token_hex(3)}@example.test"
            )

        h1, h2 = reg("pg1"), reg("pg2")
        set_nickname(client, h1, "A")
        set_nickname(client, h2, "B")
        today = seoul_today()
        created = client.post(
            "/v1/meetings",
            headers=h1,
            json={
                "title": "PG통합",
                "nickname": "A",
                "startDate": today.isoformat(),
                "endDate": (today + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(201, created.status_code, created.text)
        mid = created.json()["id"]
        code = created.json()["code"]
        cid = created.json()["collectionId"]
        self.assertEqual(
            201,
            client.post(
                "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
            ).status_code,
        )

        now = datetime.now(SEOUL)
        start = ceil_to_slot(now + timedelta(hours=5))
        end = start + timedelta(hours=2)
        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            col.scope_starts_at = ceil_to_slot(
                now.replace(hour=0, minute=0, second=0, microsecond=0)
            )
            col.scope_ends_at = end + timedelta(hours=2)
            members = {
                m.nickname: m
                for m in db.scalars(select(RoomMember).where(RoomMember.room_id == mid))
            }
            ranges = [(start, end)]
            svc.submit_response(db, room, members["A"], cid, ranges, now=now)
            svc.submit_response(db, room, members["B"], cid, ranges, now=now)
            col = db.get(ScheduleCollection, cid)
            col.grace_until = now - timedelta(seconds=1)

        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: svc.sweep(now=now), range(3)))

        with session() as db, db.begin():
            runs = list(
                db.scalars(select(ScheduleRun).where(ScheduleRun.room_id == mid))
            )
            self.assertEqual(1, len(runs))
            runs[0].ai_summary = "PostgreSQL 통합 요약입니다."

        body = client.get(f"/v1/meetings/{mid}/candidates", headers=h1).json()
        self.assertEqual("PostgreSQL 통합 요약입니다.", body["aiSummary"])
        self.assertGreaterEqual(len(body["candidates"]), 1)
        self.assertIn("memberNicknames", body["candidates"][0])
        self.assertEqual(0, svc.sweep(now=now))
