from __future__ import annotations

import hashlib
import os
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from database import initialize, session
from db_v21.models.account import Account, AccountSession
from db_v21.models.agent import AgentCandidate, AgentCandidateMember
from db_v21.models.room import Room, RoomMember
from main import app
from fastapi.testclient import TestClient


class AgentRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        initialize()
        self.client = TestClient(app)
        suffix = uuid4().hex
        self.room_id = str(uuid4())
        self.host_account_id = str(uuid4())
        self.member_account_id = str(uuid4())
        self.outsider_account_id = str(uuid4())
        self.host_member_id = str(uuid4())
        self.member_id = str(uuid4())
        self.token = secrets.token_urlsafe(32)
        self.outsider_token = secrets.token_urlsafe(32)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.path = f"/v2/rooms/{self.room_id}/agent-runs"
        self.request_body = {"expectedInputRevision": 4}

        with session() as db, db.begin():
            host = Account(
                id=self.host_account_id,
                login_email=f"host-{suffix}@example.test",
                password_hash="test-hash",
                account_type="USER",
                account_status="ACTIVE",
                approved=True,
            )
            member = Account(
                id=self.member_account_id,
                login_email=f"member-{suffix}@example.test",
                password_hash="test-hash",
                account_type="USER",
                account_status="ACTIVE",
                approved=True,
            )
            outsider = Account(
                id=self.outsider_account_id,
                login_email=f"outsider-{suffix}@example.test",
                password_hash="test-hash",
                account_type="USER",
                account_status="ACTIVE",
                approved=True,
            )
            db.add_all([host, member, outsider])
            db.flush()
            db.add(
                AccountSession(
                    account_id=host.id,
                    token_hash=hashlib.sha256(self.token.encode()).hexdigest(),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )
            db.add(
                AccountSession(
                    account_id=outsider.id,
                    token_hash=hashlib.sha256(
                        self.outsider_token.encode()
                    ).hexdigest(),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )
            room = Room(
                id=self.room_id,
                code=f"{suffix[:8]}",
                created_by_account_id=host.id,
                host_member_id=self.host_member_id,
                title="API fixture",
                starts_at=datetime(2026, 11, 5, tzinfo=timezone.utc),
                ends_at=datetime(2026, 11, 7, tzinfo=timezone.utc),
                meeting_settings={
                    "coordination": {
                        "schemaVersion": 1,
                        "activity": "Planning",
                        "location": "Seoul",
                        "durationMinutes": 60,
                        "dates": ["2026-11-05"],
                        "excludedDates": [],
                        "timeZone": "Asia/Seoul",
                        "minimumAttendeeCount": 2,
                        "absoluteTimeWindows": [],
                    }
                },
                revision=23,
                agent_input_revision=4,
            )
            db.add_all(
                [
                    room,
                    RoomMember(
                        id=self.host_member_id,
                        room_id=room.id,
                        account_id=host.id,
                        nickname="Host",
                        room_role="OWNER",
                        membership_status="ACTIVE",
                    ),
                    RoomMember(
                        id=self.member_id,
                        room_id=room.id,
                        account_id=member.id,
                        nickname="Member",
                        room_role="MEMBER",
                        membership_status="ACTIVE",
                    ),
                ]
            )

    def _create_run(self, *, idempotency_key: str = "request-key"):
        return self.client.post(
            self.path,
            headers=self.headers | {"Idempotency-Key": idempotency_key},
            json=self.request_body,
        )

    def test_authentication_and_revision_conflict_are_typed(self) -> None:
        response = self.client.post(
            self.path,
            headers={"Idempotency-Key": "missing-auth"},
            json=self.request_body,
        )
        self.assertEqual(response.status_code, 401)

        response = self.client.post(
            self.path,
            headers=self.headers | {"Idempotency-Key": "stale-request"},
            json={"expectedInputRevision": 5},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(
            response.json()["detail"],
            {
                "code": "INPUT_REVISION_CONFLICT",
                "expectedRevision": 5,
                "currentRevision": 4,
            },
        )

    def test_member_permission_and_idempotency_key_reuse_are_typed(self) -> None:
        created = self._create_run(idempotency_key="same-key")
        self.assertEqual(created.status_code, 202, created.text)
        conflict = self.client.post(
            self.path,
            headers=self.headers | {"Idempotency-Key": "same-key"},
            json={"expectedInputRevision": 3},
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(
            conflict.json()["detail"]["code"], "IDEMPOTENCY_KEY_REUSED"
        )

        forbidden = self.client.get(
            created.json()["statusUrl"],
            headers={"Authorization": f"Bearer {self.outsider_token}"},
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.text)
        self.assertEqual(
            forbidden.json()["detail"]["code"], "ROOM_MEMBERSHIP_REQUIRED"
        )

    def test_create_idempotent_status_candidates_and_cancel(self) -> None:
        created = self._create_run()
        self.assertEqual(created.status_code, 202, created.text)
        body = created.json()
        self.assertEqual(body["status"], "QUEUED")
        self.assertEqual(body["workerDispatch"], "NOT_CONFIGURED")
        self.assertEqual(body["statusUrl"], f"{self.path}/{body['runId']}")

        replay = self._create_run()
        self.assertEqual(replay.status_code, 202, replay.text)
        self.assertEqual(replay.json()["runId"], body["runId"])
        self.assertTrue(replay.json()["replayed"])

        status_response = self.client.get(body["statusUrl"], headers=self.headers)
        self.assertEqual(status_response.status_code, 200, status_response.text)
        status = status_response.json()
        self.assertEqual(status["status"], "QUEUED")
        self.assertEqual(status["inputRevision"], 4)
        self.assertNotIn("checkpoint", status_response.text.lower())
        self.assertNotIn("lease", status_response.text.lower())
        self.assertNotIn("email", status_response.text.lower())

        with session() as db, db.begin():
            candidate_id = str(uuid4())
            db.add(
                AgentCandidate(
                    id=candidate_id,
                    run_id=body["runId"],
                    rank=1,
                    source_revision=4,
                    source_snapshot_hash=status["inputSnapshotHash"],
                    meeting_date=datetime(2026, 11, 5).date(),
                    starts_at=datetime(
                        2026, 11, 5, 10, tzinfo=timezone(timedelta(hours=9))
                    ),
                    ends_at=datetime(
                        2026, 11, 5, 11, tzinfo=timezone(timedelta(hours=9))
                    ),
                    time_zone="Asia/Seoul",
                    candidate_type="ALL_AVAILABLE",
                    solver_status="OPTIMAL",
                    maximum_attendees_proven=True,
                    verified=True,
                    explanation="Verified fixture",
                )
            )
            db.add_all(
                [
                    AgentCandidateMember(
                        candidate_id=candidate_id,
                        room_member_id=self.host_member_id,
                        consent_round=1,
                        participation_status="ATTENDING",
                    ),
                    AgentCandidateMember(
                        candidate_id=candidate_id,
                        room_member_id=self.member_id,
                        consent_round=1,
                        participation_status="ATTENDING",
                    ),
                ]
            )

        candidates_response = self.client.get(
            f"{body['statusUrl']}/candidates", headers=self.headers
        )
        self.assertEqual(candidates_response.status_code, 200, candidates_response.text)
        candidates = candidates_response.json()["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["solverStatus"], "OPTIMAL")
        self.assertEqual(
            {item["roomMemberId"] for item in candidates[0]["members"]},
            {self.host_member_id, self.member_id},
        )
        self.assertNotIn("accountId", candidates_response.text)
        self.assertNotIn("email", candidates_response.text.lower())

        cancelled = self.client.post(
            f"{body['statusUrl']}/cancel", headers=self.headers
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()["status"], "CANCELLED")
        self.assertTrue(cancelled.json()["cancelRequested"])

        raced_cancel = self.client.post(
            f"{body['statusUrl']}/cancel", headers=self.headers
        )
        self.assertEqual(raced_cancel.status_code, 409)
        self.assertEqual(
            raced_cancel.json()["detail"]["code"], "AGENT_RUN_NOT_CANCELLABLE"
        )


if __name__ == "__main__":
    unittest.main()
