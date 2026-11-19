"""SSE + sweep idempotency (no DB outbox, no real Qwen)."""
from __future__ import annotations

import json
import os
import secrets
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import initialize, session
from db_v21.models.room import Room, RoomMember
from db_v21.models.schedule import ScheduleCollection, ScheduleRun
from schedule import ai_summary as summary_mod
from schedule import service as svc
from schedule.constants import SEOUL
from schedule.events import drain_pending, hub, queue_event
from schedule.router import router as schedule_router
from schedule.timeutil import ceil_to_slot, seoul_today
from user_auth import router as auth_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(schedule_router)
    return app


class ScheduleSseSweepTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # PG integration tests may leave DATABASE_URL pointing at Postgres.
        os.environ["DATABASE_URL"] = "sqlite://"
        database_module._engine = None
        initialize()
        summary_mod._background_enabled = False
        drain_pending()
        self.client = TestClient(_app())

    def tearDown(self):
        summary_mod._background_enabled = True
        drain_pending()

    def _register(self):
        email = f"s-{secrets.token_hex(4)}@example.test"
        res = self.client.post(
            "/v1/auth/register",
            json={"email": email, "password": "long-enough-password"},
        )
        self.assertEqual(201, res.status_code, res.text)
        return {"Authorization": f"Bearer {res.json()['token']}"}

    def _create(self, headers, nick="A"):
        today = seoul_today()
        res = self.client.post(
            "/v1/meetings",
            headers=headers,
            json={
                "title": "SSE모임",
                "nickname": nick,
                "startDate": today.isoformat(),
                "endDate": (today + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(201, res.status_code, res.text)
        return res.json()

    async def test_sse_receives_queued_event(self):
        h1 = self._register()
        meeting = self._create(h1)
        mid = meeting["id"]
        q = await hub.subscribe(mid)
        queue_event(mid, "member_joined", revision=3)
        from schedule.events import publish_pending_sync

        publish_pending_sync()
        item = await q.get()
        self.assertEqual("member_joined", item["event"])
        self.assertEqual(mid, item["data"]["meetingId"])
        self.assertEqual(3, item["data"]["revision"])
        await hub.unsubscribe(mid, q)

    def test_candidates_exposes_ai_summary(self):
        h1 = self._register()
        h2 = self._register()
        meeting = self._create(h1)
        mid, code, cid = meeting["id"], meeting["code"], meeting["collectionId"]
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
        )
        now = datetime.now(SEOUL)
        start = ceil_to_slot(now + timedelta(hours=4))
        end = start + timedelta(hours=2)
        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            col.scope_starts_at = ceil_to_slot(now.replace(hour=0, minute=0, second=0, microsecond=0))
            col.scope_ends_at = end + timedelta(hours=2)
            members = {
                m.nickname: m
                for m in db.scalars(select(RoomMember).where(RoomMember.room_id == mid))
            }
            ranges = [(start, end)]
            svc.submit_response(db, room, members["A"], cid, ranges, now=now)
            svc.submit_response(db, room, members["B"], cid, ranges, now=now)
            col = db.get(ScheduleCollection, cid)
            col.grace_until = now
            svc.close_collection_if_due(db, mid, now=now + timedelta(minutes=1))
            run = db.scalar(
                select(ScheduleRun)
                .where(ScheduleRun.room_id == mid)
                .order_by(ScheduleRun.created_at.desc())
            )
            run.ai_summary = "두 명이 모두 가능한 2시간 구간입니다."
        cands = self.client.get(f"/v1/meetings/{mid}/candidates", headers=h1)
        self.assertEqual(200, cands.status_code, cands.text)
        body = cands.json()
        self.assertEqual("두 명이 모두 가능한 2시간 구간입니다.", body["aiSummary"])
        self.assertGreaterEqual(len(body["candidates"]), 1)

    def test_sweep_grace_idempotent(self):
        h1 = self._register()
        h2 = self._register()
        meeting = self._create(h1)
        mid, code, cid = meeting["id"], meeting["code"], meeting["collectionId"]
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
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
            self.assertIsNotNone(col.grace_until)
            col.grace_until = now - timedelta(seconds=1)

        first = svc.sweep(now=now)
        second = svc.sweep(now=now)
        self.assertGreaterEqual(first, 1)
        self.assertEqual(0, second)
        detail = self.client.get(f"/v1/meetings/{mid}", headers=h1).json()
        self.assertIn(detail["status"], ("VOTING", "CONFIRMED"))

    def test_concurrent_sweep_safe(self):
        """Two overlapping sweeps must not double-confirm or error."""
        h1 = self._register()
        h2 = self._register()
        meeting = self._create(h1)
        mid, code, cid = meeting["id"], meeting["code"], meeting["collectionId"]
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
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

        import concurrent.futures

        # Overlapping callers must remain safe: PG races via IntegrityError;
        # SQLite StaticPool serializes inside sweep() but both threads still run.
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(svc.sweep, now=now) for _ in range(2)]
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())
        self.assertEqual(2, len(results))
        self.assertGreaterEqual(sum(results), 1)
        with session() as db:
            runs = list(
                db.scalars(select(ScheduleRun).where(ScheduleRun.room_id == mid))
            )
            self.assertEqual(1, len(runs))
            detail = self.client.get(f"/v1/meetings/{mid}", headers=h1).json()
            self.assertIn(detail["status"], ("VOTING", "CONFIRMED"))

    def test_ai_failure_does_not_break_coordination(self):
        h1 = self._register()
        h2 = self._register()
        meeting = self._create(h1)
        mid, code, cid = meeting["id"], meeting["code"], meeting["collectionId"]
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
        )
        now = datetime.now(SEOUL)
        start = ceil_to_slot(now + timedelta(hours=5))
        end = start + timedelta(hours=2)

        async def boom(*_a, **_k):
            raise RuntimeError("qwen down")

        summary_mod._background_enabled = True
        with patch.object(summary_mod, "_summary_client", boom):
            with session() as db, db.begin():
                room = db.get(Room, mid)
                col = db.get(ScheduleCollection, cid)
                col.scope_starts_at = ceil_to_slot(
                    now.replace(hour=0, minute=0, second=0, microsecond=0)
                )
                col.scope_ends_at = end + timedelta(hours=2)
                members = {
                    m.nickname: m
                    for m in db.scalars(
                        select(RoomMember).where(RoomMember.room_id == mid)
                    )
                }
                ranges = [(start, end)]
                svc.submit_response(db, room, members["A"], cid, ranges, now=now)
                svc.submit_response(db, room, members["B"], cid, ranges, now=now)
                col = db.get(ScheduleCollection, cid)
                col.grace_until = now - timedelta(seconds=1)
                ok = svc.close_collection_if_due(db, mid, now=now)
                self.assertTrue(ok)
        body = self.client.get(f"/v1/meetings/{mid}/candidates", headers=h1).json()
        self.assertGreaterEqual(len(body["candidates"]), 1)
        # summary may still be null; coordination succeeded
        self.assertIn("aiSummary", body)


if __name__ == "__main__":
    unittest.main()
