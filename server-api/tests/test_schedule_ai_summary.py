"""Qwen schedule summary — fake client only; ranking/confirm unchanged."""
from __future__ import annotations

import os
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from sqlalchemy import select

from database import initialize, session
from db_v21.base import uid
from db_v21.models.account import Account
from db_v21.models.room import Room, RoomMember
from db_v21.models.schedule import (
    ScheduleCandidate,
    ScheduleCandidateMember,
    ScheduleCollection,
    ScheduleRun,
)
from qwen_client import QwenBusy, QwenTimeout
from schedule import ai_summary as summary_mod
from schedule.constants import SEOUL


def _seed_run_with_candidates(*, summary=None):
    with session() as db, db.begin():
        a1 = Account(
            id=uid(),
            login_email=f"{uid()[:8]}@example.test",
            password_hash="x",
        )
        a2 = Account(
            id=uid(),
            login_email=f"{uid()[:8]}@example.test",
            password_hash="x",
        )
        db.add(a1)
        db.add(a2)
        db.flush()
        now = datetime.now(SEOUL)
        room = Room(
            id=uid(),
            code=uid()[:8],
            title="요약테스트",
            starts_at=now,
            ends_at=now + timedelta(days=2),
            progress_status="reviewing",
            lifecycle_status="WAITING_FOR_CONSENT",
            revision=1,
        )
        db.add(room)
        db.flush()
        owner = RoomMember(
            id=uid(),
            room_id=room.id,
            account_id=a1.id,
            nickname="감자",
            room_role="OWNER",
        )
        other = RoomMember(
            id=uid(),
            room_id=room.id,
            account_id=a2.id,
            nickname="고구마",
            room_role="MEMBER",
        )
        db.add(owner)
        db.add(other)
        db.flush()
        room.host_member_id = owner.id
        col = ScheduleCollection(
            id=uid(),
            room_id=room.id,
            cycle=0,
            kind="NORMAL",
            scope_starts_at=now,
            scope_ends_at=now + timedelta(days=1),
            closes_at=now,
            status="CLOSED",
        )
        db.add(col)
        db.flush()
        run = ScheduleRun(
            id=uid(),
            room_id=room.id,
            collection_id=col.id,
            max_count=2,
            participant_count=2,
            voter_count=2,
            ai_summary=summary,
            created_at=now,
        )
        db.add(run)
        db.flush()
        start = now + timedelta(hours=4)
        end = start + timedelta(hours=2)
        c1 = ScheduleCandidate(
            id=uid(),
            run_id=run.id,
            room_id=room.id,
            starts_at=start,
            ends_at=end,
            available_count=2,
            sort_order=1,
        )
        c2 = ScheduleCandidate(
            id=uid(),
            run_id=run.id,
            room_id=room.id,
            starts_at=start + timedelta(hours=1),
            ends_at=end + timedelta(hours=1),
            available_count=2,
            sort_order=2,
        )
        db.add(c1)
        db.add(c2)
        db.flush()
        for c in (c1, c2):
            db.add(
                ScheduleCandidateMember(
                    candidate_id=c.id, room_member_id=owner.id
                )
            )
            db.add(
                ScheduleCandidateMember(
                    candidate_id=c.id, room_member_id=other.id
                )
            )
        return run.id, c1.id, c2.id


class ScheduleAiSummaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        database_module._engine = None
        initialize()
        summary_mod._summary_client = None
        summary_mod._background_enabled = True
        with summary_mod._in_flight_guard:
            summary_mod._in_flight.clear()

    def tearDown(self):
        summary_mod._summary_client = None
        summary_mod._background_enabled = True

    async def test_fills_ai_summary_from_fake_client(self):
        run_id, c1, c2 = _seed_run_with_candidates()

        async def fake(_run_id, payload):
            self.assertEqual(2, len(payload["candidates"]))
            self.assertEqual(1, payload["candidates"][0]["rank"])
            self.assertIn("감자", payload["candidates"][0]["nicknames"])
            return "두 후보 모두 2명이 가능하며 1순위가 더 이릅니다."

        summary_mod._summary_client = fake
        await summary_mod.fill_ai_summary(run_id)

        with session() as db:
            run = db.get(ScheduleRun, run_id)
            self.assertEqual(
                "두 후보 모두 2명이 가능하며 1순위가 더 이릅니다.", run.ai_summary
            )
            cands = list(
                db.scalars(
                    select(ScheduleCandidate)
                    .where(ScheduleCandidate.run_id == run_id)
                    .order_by(ScheduleCandidate.sort_order)
                )
            )
            self.assertEqual([1, 2], [c.sort_order for c in cands])
            self.assertEqual([c1, c2], [c.id for c in cands])

    async def test_timeout_leaves_null_and_candidates_intact(self):
        run_id, c1, c2 = _seed_run_with_candidates()

        async def boom(_run_id, _payload):
            raise QwenTimeout()

        summary_mod._summary_client = boom
        await summary_mod.fill_ai_summary(run_id)

        with session() as db:
            run = db.get(ScheduleRun, run_id)
            self.assertIsNone(run.ai_summary)
            cands = list(
                db.scalars(
                    select(ScheduleCandidate)
                    .where(ScheduleCandidate.run_id == run_id)
                    .order_by(ScheduleCandidate.sort_order)
                )
            )
            self.assertEqual([c1, c2], [c.id for c in cands])
            self.assertEqual([1, 2], [c.sort_order for c in cands])
            self.assertEqual([2, 2], [c.available_count for c in cands])

    async def test_busy_skips_without_writing(self):
        run_id, _, _ = _seed_run_with_candidates()

        async def busy(_run_id, _payload):
            raise QwenBusy()

        summary_mod._summary_client = busy
        await summary_mod.fill_ai_summary(run_id)
        with session() as db:
            self.assertIsNone(db.get(ScheduleRun, run_id).ai_summary)

    async def test_invalid_prose_rejected(self):
        run_id, _, _ = _seed_run_with_candidates()

        async def bad(_run_id, _payload):
            return '{"rank": 99}'

        summary_mod._summary_client = bad
        await summary_mod.fill_ai_summary(run_id)
        with session() as db:
            self.assertIsNone(db.get(ScheduleRun, run_id).ai_summary)

    async def test_normalize_truncates(self):
        self.assertEqual(200, len(summary_mod._normalize_summary("가" * 250)))

    def test_enqueue_dedupes_inflight(self):
        run_id, _, _ = _seed_run_with_candidates()
        gate = {"go": False, "entered": False}

        async def slow(_run_id, _payload):
            gate["entered"] = True
            while not gate["go"]:
                await __import__("asyncio").sleep(0.01)
            return "ok"

        summary_mod._summary_client = slow
        summary_mod.enqueue_ai_summary(run_id)
        for _ in range(200):
            if gate["entered"]:
                break
            time.sleep(0.01)
        self.assertTrue(gate["entered"])
        summary_mod.enqueue_ai_summary(run_id)
        with summary_mod._in_flight_guard:
            self.assertEqual({run_id}, summary_mod._in_flight)
        gate["go"] = True
        for _ in range(200):
            with summary_mod._in_flight_guard:
                if run_id not in summary_mod._in_flight:
                    break
            time.sleep(0.01)
        with session() as db:
            self.assertEqual("ok", db.get(ScheduleRun, run_id).ai_summary)

    async def test_chat_completion_path_mocked(self):
        run_id, _, _ = _seed_run_with_candidates()

        async def fake_chat(*_a, **_k):
            return "1순위는 4시간 뒤 2시간 구간으로 감자·고구마가 가능합니다."

        with patch.object(summary_mod, "chat_completion", fake_chat):
            await summary_mod.fill_ai_summary(run_id)
        with session() as db:
            self.assertIn("1순위", db.get(ScheduleRun, run_id).ai_summary)


if __name__ == "__main__":
    unittest.main()
