"""HTTP tests for the Agent decision endpoints (TestClient, SQLite)."""
from __future__ import annotations

import hashlib
import os
import secrets
import unittest
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module  # noqa: E402

database_module._engine = None

import agent_routes  # noqa: E402
from database import initialize  # noqa: E402
from db_v21.models.account import AccountSession  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from services.agent_worker import claim_next_agent_run, execute_agent_run  # noqa: E402
from tests import test_meeting_snapshot  # noqa: E402
from tests.test_agent_resume import sqlite_saver  # noqa: E402

import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402


class DecisionRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        database_module._engine = None
        initialize()
        self.h = test_meeting_snapshot.MeetingSnapshotBuilderTests("setUp")
        self.h.engine = database_module.engine()
        self.h.db = Session(self.h.engine)
        self.h._insert_fixture()
        self.addCleanup(self.h.db.close)
        self.addCleanup(setattr, agent_routes, "_checkpointer_override", None)
        factory = lambda: Session(self.h.engine)  # noqa: E731
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cm = sqlite_saver(Path(tmp.name) / "ckpt.sqlite")
        saver = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        agent_routes._checkpointer_override = saver

        run = self.h._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(factory, worker_id="w", lease_seconds=30)
        result = execute_agent_run(claim, factory, lease_seconds=30, checkpointer=saver)
        self.run_id = run.run_id
        self.candidate_id = result.candidates[0].candidate.candidate_id
        self.tokens = {}
        with Session(self.h.engine) as db:
            for key in ("host", "member", "no-submission", "pending"):
                token = secrets.token_urlsafe(24)
                self.tokens[key] = token
                db.add(AccountSession(
                    account_id=f"account-{key}",
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                ))
            db.commit()
        self.client = TestClient(app)
        self.base = f"/v2/rooms/room-1/agent-runs/{self.run_id}"

    def _post(self, who, path, body):
        return self.client.post(
            f"{self.base}/{path}", json=body,
            headers={"Authorization": f"Bearer {self.tokens[who]}"},
        )

    def _get(self, who, path):
        return self.client.get(
            f"{self.base}/{path}", headers={"Authorization": f"Bearer {self.tokens[who]}"}
        )

    def test_full_http_flow(self) -> None:
        self.assertEqual(self._get("host", "decision").json()["selectedCandidateId"], None)
        r = self._post("host", "select", {"candidateId": self.candidate_id, "expectedVersion": 0})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body["decisionVersion"], body["graphSync"], body["consentRound"]), (1, "SYNCED", 1))
        for who in ("host", "member", "no-submission"):
            r = self._post(who, "consent", {"decision": "AGREE"})
            self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["status"], r.json()["approvalStatus"]), ("AWAITING_APPROVAL", "PENDING"))
        r = self._post("host", "approval", {"decision": "APPROVE"})
        self.assertEqual((r.status_code, r.json()["approvalStatus"], r.json()["finalized"]), (200, "APPROVED", False))
        r = self._post("host", "finalize", {})
        self.assertEqual((r.status_code, r.json()["finalized"]), (200, True))
        self.assertEqual(self._post("host", "finalize", {}).json()["changed"], False)

    def test_final_result_contract_over_http(self) -> None:
        url = "/v2/rooms/room-1/agent-final-result"
        auth = {"Authorization": f"Bearer {self.tokens['member']}"}
        before = self.client.get(url, headers=auth)
        self.assertEqual((before.status_code, before.json()["finalized"]), (200, False))
        self._post("host", "select", {"candidateId": self.candidate_id})
        for who in ("host", "member", "no-submission"):
            self._post(who, "consent", {"decision": "AGREE"})
        self._post("host", "approval", {"decision": "APPROVE"})
        self._post("host", "finalize", {})
        body = self.client.get(url, headers=auth).json()
        self.assertEqual(
            (body["finalized"], body["runId"], body["candidateId"], body["inputCurrent"]),
            (True, self.run_id, self.candidate_id, True),
        )
        self.assertEqual(len(body["attendeeMemberIds"]), 3)
        self.assertEqual(body["roomProgressStatus"], "collecting")  # /v1 state untouched
        self.assertEqual(self.client.get(url).status_code, 401)
        outsider = {"Authorization": f"Bearer {self.tokens['pending']}"}
        self.assertEqual(self.client.get(url, headers=outsider).status_code, 403)

    def _finalize_over_http(self) -> None:
        self._post("host", "select", {"candidateId": self.candidate_id})
        for who in ("host", "member", "no-submission"):
            self._post(who, "consent", {"decision": "AGREE"})
        self._post("host", "approval", {"decision": "APPROVE"})
        self.assertEqual(self._post("host", "finalize", {}).status_code, 200)

    def _round_post(self, who, key, body, *, headers_key=True):
        headers = {"Authorization": f"Bearer {self.tokens[who]}"}
        if headers_key:
            headers["Idempotency-Key"] = key
        return self.client.post("/v2/rooms/room-1/coordination-rounds", json=body, headers=headers)

    def test_start_run_is_refused_in_a_finalized_round_and_allowed_after_a_new_round(self) -> None:
        self._finalize_over_http()
        runs = "/v2/rooms/room-1/agent-runs"
        headers = {"Authorization": f"Bearer {self.tokens['host']}", "Idempotency-Key": "late-run"}
        blocked = self.client.post(runs, json={"expectedInputRevision": 5}, headers=headers)
        self.assertEqual((blocked.status_code, blocked.json()["detail"]["code"]), (409, "ROUND_ALREADY_FINALIZED"))

        opened = self._round_post("host", "round-1", {"expectedRound": 0, "reason": "재조정"})
        self.assertEqual(opened.status_code, 200, opened.text)
        body = opened.json()
        self.assertEqual((body["fromRound"], body["toRound"], body["closedRunId"], body["changed"]),
                         (0, 1, self.run_id, True))
        allowed = self.client.post(
            runs, json={"expectedInputRevision": body["openedInputRevision"]},
            headers={**headers, "Idempotency-Key": "next-run"},
        )
        self.assertEqual((allowed.status_code, allowed.json()["status"]), (202, "QUEUED"))
        result = self.client.get(
            "/v2/rooms/room-1/agent-final-result",
            headers={"Authorization": f"Bearer {self.tokens['member']}"},
        ).json()
        self.assertEqual((result["finalized"], result["coordinationRound"], result["roomRound"]), (False, 1, 1))

    def test_coordination_round_endpoint_contract(self) -> None:
        body = {"expectedRound": 0}
        self.assertEqual(self.client.post("/v2/rooms/room-1/coordination-rounds", json=body).status_code, 401)
        self.assertEqual(self._round_post("host", "k", body, headers_key=False).json()["detail"]["code"],
                         "IDEMPOTENCY_KEY_REQUIRED")
        not_final = self._round_post("host", "k1", body)
        self.assertEqual((not_final.status_code, not_final.json()["detail"]["code"]), (409, "ROUND_NOT_FINALIZED"))
        self._finalize_over_http()
        self.assertEqual(self._round_post("member", "k2", body).status_code, 403)
        self.assertEqual(self._round_post("host", "k3", {"expectedRound": -1}).status_code, 422)
        self.assertEqual(self._round_post("host", "k4", {"expectedRound": 3}).json()["detail"]["code"],
                         "COORDINATION_ROUND_CONFLICT")
        first = self._round_post("host", "k5", body)
        replay = self._round_post("host", "k5", body)
        self.assertEqual((first.status_code, replay.status_code), (200, 200))
        self.assertEqual((replay.json()["changed"], replay.json()["id"]), (False, first.json()["id"]))
        self.assertEqual(self._round_post("host", "k5", {"expectedRound": 0, "reason": "다름"}).status_code, 409)

    def test_existing_run_and_candidate_responses_are_unchanged_in_shape(self) -> None:
        self._post("host", "select", {"candidateId": self.candidate_id})
        run = self._get("host", "").json()
        self.assertEqual(
            set(run),
            {"runId", "status", "inputRevision", "inputSnapshotHash", "errorCode",
             "cancelRequested", "createdAt", "startedAt", "completedAt"},
        )
        candidates = self._get("host", "candidates").json()
        self.assertEqual(len(candidates["candidates"][0]["members"]), 3)

    def test_candidate_list_shows_only_the_latest_round(self) -> None:
        self._post("host", "select", {"candidateId": self.candidate_id})
        self._post("host", "select", {"candidateId": self.candidate_id})
        members = self._get("host", "candidates").json()["candidates"][0]["members"]
        self.assertEqual(len(members), 3)
        self.assertEqual({m["consentRound"] for m in members}, {2})

    def test_authorization_and_error_mapping(self) -> None:
        body = {"candidateId": self.candidate_id}
        self.assertEqual(self._post("member", "select", body).status_code, 403)
        self.assertEqual(self._post("pending", "select", body).status_code, 403)
        self.assertEqual(
            self.client.post(f"{self.base}/select", json=body).status_code, 401
        )
        self.assertEqual(self._post("host", "select", {"candidateId": "nope"}).status_code, 404)
        self.assertEqual(self._post("host", "select", {**body, "expectedVersion": 5}).status_code, 409)
        self.assertEqual(self._post("member", "consent", {"decision": "AGREE"}).json()["detail"]["code"],
                         "NO_CANDIDATE_SELECTED")
        self.assertEqual(self._post("host", "consent", {"decision": "MAYBE"}).status_code, 422)
        self.assertEqual(self._post("host", "approval", {"decision": "APPROVE"}).status_code, 409)
        self.assertEqual(self._post("host", "finalize", {}).json()["detail"]["code"], "APPROVAL_REQUIRED")
        self.assertEqual(self._post("host", "select", {**body, "extra": 1}).status_code, 422)

    def test_stale_meeting_returns_conflict_and_marks_run(self) -> None:
        from db_v21.models.room import Room

        with Session(self.h.engine) as db:
            db.get(Room, "room-1").agent_input_revision = 9
            db.commit()
        r = self._post("host", "select", {"candidateId": self.candidate_id})
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "STALE_AGENT_RUN"))
        self.assertEqual(self._get("host", "").json()["status"], "STALE")

    def test_decisions_work_without_a_checkpointer(self) -> None:
        agent_routes._checkpointer_override = None
        r = self._post("host", "select", {"candidateId": self.candidate_id})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["graphSync"], "PENDING")  # durable ref exists but unsynced


if __name__ == "__main__":
    unittest.main()


class CheckpointerLifetimeTests(unittest.TestCase):
    """Regression: the PostgreSQL saver pool was closed by garbage collection."""

    def test_the_pool_stays_open_after_the_provider_returns(self) -> None:
        import gc
        from contextlib import contextmanager
        from unittest.mock import patch

        closed = []

        @contextmanager
        def fake_open(url):
            try:
                yield object()
            finally:
                closed.append(url)

        import agent_routes

        agent_routes._checkpointer_singleton = agent_routes._checkpointer_stack = None
        try:
            with patch.dict("os.environ", {"AGENT_CHECKPOINT_DATABASE_URL": "postgresql://x/y"}), patch(
                "potato_agent.checkpoint.open_postgres_checkpointer", fake_open
            ):
                saver = agent_routes._checkpointer()
                gc.collect()
                self.assertEqual(closed, [])  # still open
                self.assertIs(agent_routes._checkpointer(), saver)  # a singleton
        finally:
            if agent_routes._checkpointer_stack is not None:
                agent_routes._checkpointer_stack.close()
            agent_routes._checkpointer_singleton = agent_routes._checkpointer_stack = None
