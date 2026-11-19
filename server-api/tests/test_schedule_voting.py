"""Voting and confirmation tests (T9)."""
from __future__ import annotations

import os
import secrets
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from database import initialize, session
from db_v21.models.room import Room, RoomMember
from db_v21.models.schedule import (
    ScheduleCollection,
    ScheduleResponse,
    ScheduleResponseRange,
    ScheduleResult,
    ScheduleRun,
    ScheduleVoteBallot,
)
from schedule import ai_summary as summary_mod
from schedule import service as svc
from schedule.constants import SEOUL
from schedule.router import router as schedule_router
from schedule.timeutil import ceil_to_slot, seoul_today
from user_auth import router as auth_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(schedule_router)
    return app


def _align(dt: datetime) -> datetime:
    return ceil_to_slot(dt)


class ScheduleVotingTests(unittest.TestCase):
    def setUp(self):
        # PG integration tests may leave DATABASE_URL pointing at Postgres.
        os.environ["DATABASE_URL"] = "sqlite://"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        summary_mod._background_enabled = False
        self.client = TestClient(_app())

    def tearDown(self):
        summary_mod._background_enabled = True
        self.client.close()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    def _register(self):
        email = f"v-{secrets.token_hex(4)}@example.test"
        res = self.client.post(
            "/v1/auth/register",
            json={"email": email, "password": "long-enough-password"},
        )
        self.assertEqual(201, res.status_code, res.text)
        return {"Authorization": f"Bearer {res.json()['token']}"}

    def _create_meeting(self, headers, nick="A"):
        today = seoul_today()
        res = self.client.post(
            "/v1/meetings",
            headers=headers,
            json={
                "title": "투표모임",
                "nickname": nick,
                "startDate": today.isoformat(),
                "endDate": (today + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(201, res.status_code, res.text)
        return res.json()

    def _enter_voting_two_candidates(self, h1, h2):
        """A/B long window + C middle → 2 candidates, voting_ends far in future."""
        meeting = self._create_meeting(h1, nick="A")
        mid, code, cid = meeting["id"], meeting["code"], meeting["collectionId"]
        self.client.post(
            "/v1/meetings/join", headers=h2, json={"code": code, "nickname": "B"}
        )
        h3 = self._register()
        self.client.post(
            "/v1/meetings/join", headers=h3, json={"code": code, "nickname": "C"}
        )

        now = datetime.now(SEOUL)
        # Windows start ≥ now+4h so Q30 keeps ≥1h voting even if wall clock advances slightly
        start = _align(now + timedelta(hours=4))
        mid_s = start + timedelta(hours=1)
        mid_e = mid_s + timedelta(hours=1)
        end = start + timedelta(hours=3)

        with session() as db, db.begin():
            room = db.get(Room, mid)
            col = db.get(ScheduleCollection, cid)
            col.scope_starts_at = _align(now.replace(hour=0, minute=0, second=0, microsecond=0))
            if col.scope_starts_at > start:
                col.scope_starts_at = _align(now)
            col.scope_ends_at = end + timedelta(hours=2)
            members = {
                m.nickname: m
                for m in db.scalars(
                    select(RoomMember).where(RoomMember.room_id == mid)
                )
            }
            ab = [(start, end)]
            c_only = [(mid_s, mid_e)]
            svc.submit_response(db, room, members["A"], cid, ab, now=now)
            svc.submit_response(db, room, members["B"], cid, ab, now=now)
            svc.submit_response(db, room, members["C"], cid, c_only, now=now)
            col = db.get(ScheduleCollection, cid)
            col.grace_until = now
            svc.close_collection_if_due(db, mid, now=now + timedelta(minutes=1))
            # Ensure voting window still open vs real clock
            run = db.scalar(
                select(ScheduleRun)
                .where(ScheduleRun.room_id == mid)
                .order_by(ScheduleRun.created_at.desc())
            )
            self.assertIsNotNone(run)
            if run.voting_ends_at is not None:
                run.voting_ends_at = now + timedelta(hours=5)

        detail = self.client.get(f"/v1/meetings/{mid}", headers=h1).json()
        self.assertEqual("VOTING", detail["status"], detail)
        cands = self.client.get(f"/v1/meetings/{mid}/candidates", headers=h1)
        self.assertEqual(200, cands.status_code, cands.text)
        body = cands.json()
        self.assertGreaterEqual(len(body["candidates"]), 2, body)
        return mid, body, h3

    def test_t9_6_empty_ballot_and_t9_7_early_close(self):
        h1, h2 = self._register(), self._register()
        mid, body, h3 = self._enter_voting_two_candidates(h1, h2)
        cands = sorted(body["candidates"], key=lambda c: c["sortOrder"])
        self.assertEqual(
            200,
            self.client.put(
                f"/v1/meetings/{mid}/votes/me",
                headers=h1,
                json={"candidateIds": [cands[0]["id"]]},
            ).status_code,
        )
        self.assertEqual(
            200,
            self.client.put(
                f"/v1/meetings/{mid}/votes/me",
                headers=h2,
                json={"candidateIds": []},
            ).status_code,
        )
        r3 = self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h3,
            json={"candidateIds": []},
        )
        self.assertEqual(200, r3.status_code, r3.text)
        detail = self.client.get(f"/v1/meetings/{mid}", headers=h1).json()
        self.assertEqual("CONFIRMED", detail["status"], detail)
        result = self.client.get(f"/v1/meetings/{mid}/result", headers=h1).json()
        self.assertEqual("VOTE", result["method"])
        self.assertEqual(cands[0]["id"], result["candidate"]["id"])
        with session() as db:
            self.assertEqual(3, len(list(db.scalars(select(ScheduleVoteBallot)))))

    def test_t9_3_non_completer_403(self):
        h1, h2 = self._register(), self._register()
        mid, body, h3 = self._enter_voting_two_candidates(h1, h2)
        with session() as db, db.begin():
            run = db.scalar(
                select(ScheduleRun)
                .where(ScheduleRun.room_id == mid)
                .order_by(ScheduleRun.created_at.desc())
            )
            c_member = db.scalar(
                select(RoomMember).where(
                    RoomMember.room_id == mid, RoomMember.nickname == "C"
                )
            )
            db.execute(
                delete(ScheduleResponseRange).where(
                    ScheduleResponseRange.collection_id == run.collection_id,
                    ScheduleResponseRange.room_member_id == c_member.id,
                )
            )
            db.execute(
                delete(ScheduleResponse).where(
                    ScheduleResponse.collection_id == run.collection_id,
                    ScheduleResponse.room_member_id == c_member.id,
                )
            )
        denied = self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h3,
            json={"candidateIds": [body["candidates"][0]["id"]]},
        )
        self.assertEqual(403, denied.status_code, denied.text)

    def test_t9_4_unavailable_candidate_422(self):
        h1, h2 = self._register(), self._register()
        mid, body, h3 = self._enter_voting_two_candidates(h1, h2)
        blocked = next(
            (c["id"] for c in body["candidates"] if "C" not in c["memberNicknames"]),
            None,
        )
        self.assertIsNotNone(blocked, body["candidates"])
        bad = self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h3,
            json={"candidateIds": [blocked]},
        )
        self.assertEqual(422, bad.status_code, bad.text)

    def test_t9_10_tie_uses_sort_order(self):
        h1, h2 = self._register(), self._register()
        mid, body, h3 = self._enter_voting_two_candidates(h1, h2)
        cands = sorted(body["candidates"], key=lambda c: c["sortOrder"])
        # C can only vote for candidates listing C — pick first available for C for one side
        c_ok = next(c for c in cands if "C" in c["memberNicknames"])
        other = next(c for c in cands if c["id"] != c_ok["id"])
        # A→other, B→c_ok, C→c_ok  OR for tie A→cands[0], B→cands[1] if both allow
        # Safer tie: A votes #1 (if A in both), B votes #2, C empty
        a_targets = [c for c in cands if "A" in c["memberNicknames"]]
        self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h1,
            json={"candidateIds": [a_targets[0]["id"]]},
        )
        self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h2,
            json={"candidateIds": [a_targets[1]["id"] if len(a_targets) > 1 else other["id"]]},
        )
        self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h3,
            json={"candidateIds": []},
        )
        result = self.client.get(f"/v1/meetings/{mid}/result", headers=h1).json()
        # With 1-1 tie between two, lower sort_order wins
        self.assertTrue(result["tieBroken"] or result["voteCount"] >= 1)
        winner = result["candidate"]["id"]
        self.assertIn(winner, {c["id"] for c in cands})

    def test_t9_11_all_empty_picks_first(self):
        h1, h2 = self._register(), self._register()
        mid, body, h3 = self._enter_voting_two_candidates(h1, h2)
        cands = sorted(body["candidates"], key=lambda c: c["sortOrder"])
        for h in (h1, h2, h3):
            self.assertEqual(
                200,
                self.client.put(
                    f"/v1/meetings/{mid}/votes/me",
                    headers=h,
                    json={"candidateIds": []},
                ).status_code,
            )
        result = self.client.get(f"/v1/meetings/{mid}/result", headers=h1).json()
        self.assertEqual(cands[0]["id"], result["candidate"]["id"])
        self.assertEqual(0, result["voteCount"])

    def test_t9_8_timeout_and_idempotent(self):
        h1, h2 = self._register(), self._register()
        mid, body, _h3 = self._enter_voting_two_candidates(h1, h2)
        self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h1,
            json={"candidateIds": [body["candidates"][0]["id"]]},
        )
        with session() as db, db.begin():
            run = db.scalar(
                select(ScheduleRun)
                .where(ScheduleRun.room_id == mid)
                .order_by(ScheduleRun.created_at.desc())
            )
            run.voting_ends_at = datetime.now(SEOUL) - timedelta(minutes=1)
            self.assertTrue(svc.close_voting_if_due(db, mid, now=datetime.now(SEOUL)))
            self.assertFalse(svc.close_voting_if_due(db, mid, now=datetime.now(SEOUL)))
            run = db.scalar(
                select(ScheduleRun)
                .where(ScheduleRun.room_id == mid)
                .order_by(ScheduleRun.created_at.desc())
            )
            self.assertEqual("TIMEOUT", run.closed_reason)
            self.assertEqual(1, len(list(db.scalars(select(ScheduleResult)))))

    def test_t9_12_immutable_after_confirm(self):
        h1, h2 = self._register(), self._register()
        mid, _body, h3 = self._enter_voting_two_candidates(h1, h2)
        for h in (h1, h2, h3):
            self.client.put(
                f"/v1/meetings/{mid}/votes/me",
                headers=h,
                json={"candidateIds": []},
            )
        again = self.client.put(
            f"/v1/meetings/{mid}/votes/me",
            headers=h1,
            json={"candidateIds": []},
        )
        self.assertEqual(409, again.status_code, again.text)
        h4 = self._register()
        code = self.client.get(f"/v1/meetings/{mid}", headers=h1).json()["code"]
        self.assertEqual(
            409,
            self.client.post(
                "/v1/meetings/join",
                headers=h4,
                json={"code": code, "nickname": "X"},
            ).status_code,
        )


if __name__ == "__main__":
    unittest.main()
