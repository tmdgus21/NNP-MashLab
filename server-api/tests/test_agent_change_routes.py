"""HTTP tests for /v2/rooms/{room}/agent-change-proposals (TestClient, fake Qwen)."""
from __future__ import annotations

import hashlib
import os
import secrets
import unittest
from datetime import date, datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module  # noqa: E402

database_module._engine = None

from database import initialize  # noqa: E402
from db_v21.models.account import AccountSession  # noqa: E402
from db_v21.models.agent import AgentRun  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from potato_agent.llama_cpp import LlamaCppError  # noqa: E402
from services import agent_change as ac  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from tests import test_meeting_snapshot  # noqa: E402
from tests.test_agent_change import DURATION_45, FakeQwen, TODAY  # noqa: E402


class ChangeRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        database_module._engine = None
        initialize()
        self.h = test_meeting_snapshot.MeetingSnapshotBuilderTests("setUp")
        self.h.engine = database_module.engine()
        self.h.db = Session(self.h.engine)
        self.h._insert_fixture()
        self.addCleanup(self.h.db.close)
        self.run_id = self.h._create_solver_run(no_submission_start_minute=540).run_id
        self.tokens = {}
        with Session(self.h.engine) as db:
            for key in ("host", "member", "pending"):
                token = secrets.token_urlsafe(24)
                self.tokens[key] = token
                db.add(AccountSession(
                    account_id=f"account-{key}",
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                ))
            db.commit()
        self.addCleanup(setattr, ac, "agent_factory", ac.agent_factory)
        self.addCleanup(setattr, ac, "_today", ac._today)
        ac._today = lambda: TODAY
        ac.agent_factory = FakeQwen([DURATION_45])
        self.client = TestClient(app)
        self.base = "/v2/rooms/room-1/agent-change-proposals"

    def _headers(self, who, key=None):
        headers = {"Authorization": f"Bearer {self.tokens[who]}"}
        if key:
            headers["Idempotency-Key"] = key
        return headers

    def _create(self, who="host", key="key-1", text="회의 시간을 45분으로"):
        return self.client.post(
            self.base, json={"requestText": text}, headers=self._headers(who, key)
        )

    def test_propose_approve_and_recompute_queue(self) -> None:
        r = self._create()
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body["status"], body["baseInputRevision"], body["resultingRunId"]), ("PROPOSED", 5, None))
        self.assertEqual(body["changes"][0]["kind"], "SET_DURATION")

        again = self._create()
        self.assertEqual((again.json()["proposalId"], again.json()["changed"]), (body["proposalId"], False))

        approved = self.client.post(f"{self.base}/{body['proposalId']}/approve", headers=self._headers("host"))
        self.assertEqual(approved.status_code, 200, approved.text)
        data = approved.json()
        self.assertEqual((data["status"], data["appliedInputRevision"]), ("APPLIED", 6))
        with Session(self.h.engine) as db:
            self.assertEqual(db.get(AgentRun, self.run_id).status, "STALE")
            new = db.get(AgentRun, data["resultingRunId"])
            self.assertEqual((new.status, new.source_revision), ("QUEUED", 6))
        replay = self.client.post(f"{self.base}/{body['proposalId']}/approve", headers=self._headers("host"))
        self.assertEqual((replay.status_code, replay.json()["changed"]), (200, False))
        got = self.client.get(f"{self.base}/{body['proposalId']}", headers=self._headers("host"))
        self.assertEqual(got.json()["status"], "APPLIED")

    def test_auth_and_error_mapping(self) -> None:
        self.assertEqual(self.client.post(self.base, json={"requestText": "x"}).status_code, 401)
        no_key = self.client.post(self.base, json={"requestText": "x"}, headers=self._headers("host"))
        self.assertEqual((no_key.status_code, no_key.json()["detail"]["code"]), (400, "IDEMPOTENCY_KEY_REQUIRED"))
        self.assertEqual(self._create(who="pending").status_code, 403)
        self.assertEqual(self._create(text="  ").status_code, 422)
        self.assertEqual(self._create(who="member").json()["detail"]["code"], "HOST_REQUIRED")
        self.assertEqual(self._create(text="다른", key="key-1").status_code, 200)  # new text, same key on empty -> first use
        self.assertEqual(self._create(text="또 다른", key="key-1").json()["detail"]["code"], "IDEMPOTENCY_KEY_REUSED")

    def test_only_requester_approves_and_reject_blocks_apply(self) -> None:
        proposal_id = self._create().json()["proposalId"]
        forbidden = self.client.post(f"{self.base}/{proposal_id}/approve", headers=self._headers("member"))
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(
            self.client.get(f"{self.base}/{proposal_id}", headers=self._headers("member")).status_code, 403
        )
        rejected = self.client.post(f"{self.base}/{proposal_id}/reject", headers=self._headers("host"))
        self.assertEqual(rejected.json()["status"], "REJECTED")
        late = self.client.post(f"{self.base}/{proposal_id}/approve", headers=self._headers("host"))
        self.assertEqual((late.status_code, late.json()["detail"]["code"]), (409, "PROPOSAL_NOT_APPROVABLE"))
        missing = self.client.post(f"{self.base}/nope/approve", headers=self._headers("host"))
        self.assertEqual(missing.status_code, 404)

    def test_409_is_returned_only_after_superseded_is_committed(self) -> None:
        proposal_id = self._create().json()["proposalId"]
        with Session(self.h.engine) as db:  # another edit lands first
            from db_v21.models.room import Room

            db.get(Room, "room-1").agent_input_revision = 6
            db.commit()
        r = self.client.post(f"{self.base}/{proposal_id}/approve", headers=self._headers("host"))
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "STALE_PROPOSAL"))
        got = self.client.get(f"{self.base}/{proposal_id}", headers=self._headers("host"))
        self.assertEqual(got.json()["status"], "SUPERSEDED")  # visible to a new request

    def test_finalized_round_blocks_new_proposals_with_409(self) -> None:
        with Session(self.h.engine) as db:
            run = db.get(AgentRun, self.run_id)
            run.finalized_at = datetime.now(timezone.utc)
            run.finalized_room_round = 0
            db.commit()
        r = self._create()
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "ROUND_ALREADY_FINALIZED"))

    def test_qwen_outage_is_503_and_stores_nothing(self) -> None:
        ac.agent_factory = FakeQwen(raises=LlamaCppError("QWEN_UNREACHABLE", "down"))
        r = self._create()
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (503, "QWEN_UNAVAILABLE"))
        ac.agent_factory = FakeQwen([DURATION_45])
        self.assertEqual(self._create().status_code, 200)  # same key is usable after the failure


if __name__ == "__main__":
    unittest.main()
