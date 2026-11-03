"""/v1 role assignment vs Potato Meet: boundary guards and /v1 backward compatibility."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module  # noqa: E402

database_module._engine = None

from database import Member, initialize, session  # noqa: E402
from db_v21.models.agent import AgentRun  # noqa: E402
from db_v21.models.room import Room  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from sqlalchemy import select  # noqa: E402
from workflow_models import Conditions  # noqa: E402

CONFIG = {"title": "경계 검증", "name": "방장", "dates": ["2026-10-17"], "roles": ["진행", "기록"],
          "roleNeeds": {"진행": 1, "기록": 1}, "duration": 60, "windowStart": 540, "windowEnd": 720}


def conditions(roles, **extra):
    return Conditions(
        roles=roles, availability=[{"date": "2026-10-17", "start": 540, "end": 720}], **extra
    ).model_dump()


class BoundaryBase(unittest.TestCase):
    def setUp(self) -> None:
        database_module._engine = None
        initialize()
        self.client = TestClient(app)
        self.host = self.client.post("/v1/meetings", json=CONFIG).json()
        self.id = self.host["meeting"]["id"]
        self.code = self.host["meeting"]["code"]

    def headers(self, actor):
        return {"Authorization": "Bearer " + actor["token"]}

    def get(self):
        return self.client.get("/v1/meetings/" + self.id, headers=self.headers(self.host)).json()

    def mutate(self, path, actor=None, method="post", **body):
        return getattr(self.client, method)(
            "/v1/meetings/" + self.id + path,
            headers=self.headers(actor or self.host),
            json={"expectedRevision": self.get()["revision"], **body},
        )

    def room(self) -> Room:
        with session() as db:
            room = db.get(Room, self.id)
            db.expunge(room)
            return room

    def make_potato(self) -> None:
        """A /v1-created room that also carries the Agent coordination block."""
        with session() as db, db.begin():
            room = db.get(Room, self.id)
            room.meeting_settings = {**room.meeting_settings, "coordination": {"schemaVersion": 1}}

    def add_final_agent_run(self, round_: int = 0) -> None:
        with session() as db, db.begin():
            db.add(AgentRun(
                agent_session_id="s", room_id=self.id, source_revision=1,
                input_snapshot_hash="0" * 64, input_snapshot={}, status="AWAITING_APPROVAL",
                finalized_at=datetime.now(timezone.utc), finalized_room_round=round_,
            ))


class PlainV1RoomTests(BoundaryBase):
    """Rooms without a coordination block behave exactly as before."""

    def test_v1_flow_is_unchanged_and_never_touches_agent_revision(self) -> None:
        guest = self.client.post("/v1/meetings/join", json={"code": self.code, "name": "참여자"}).json()
        self.assertEqual(self.mutate("/conditions", method="put", conditions=conditions(["진행"], requiredRoles=["진행"])).status_code, 200)
        self.assertEqual(self.mutate("/conditions", guest, method="put", conditions=conditions(["기록"])).status_code, 200)
        self.assertEqual(self.mutate("/calculations").status_code, 200)
        self.assertEqual(self.room().agent_input_revision, 1)  # default; no bump for /v1 rooms
        self.assertEqual(self.room().coordination_round, 0)


class PotatoRoomBoundaryTests(BoundaryBase):
    def test_role_assignment_endpoints_are_refused_for_potato_rooms(self) -> None:
        self.make_potato()
        for response in (
            self.mutate("/calculations"),
            self.mutate("/consent", method="put", consent="agreed", note="", round=1),
            self.mutate("/finalize"),
        ):
            self.assertEqual(response.status_code, 409, response.text)
            self.assertIn("Potato Meet", response.json()["detail"])
        with patch("workflow.admin_enabled", return_value=True):
            response = self.client.post(
                f"/v1/meetings/{self.id}/extensions", headers=self.headers(self.host),
                json={"expectedRevision": self.room().revision, "dates": ["2027-01-01"], "reason": "연장 사유입니다"},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.room().progress_status, "collecting")  # nothing was finalized

    def test_v1_join_is_refused_for_potato_rooms_and_v1_condition_submit_advances_the_revision(self) -> None:
        self.make_potato()
        before = self.room()
        join = self.client.post("/v1/meetings/join", json={"code": self.code, "name": "참여자"})
        self.assertEqual((join.status_code, join.json()["detail"]), (409, "Potato Meet 모임은 /v2/rooms/join으로 참가하세요."))
        self.assertEqual(self.room().agent_input_revision, before.agent_input_revision)  # nothing joined
        submitted = self.mutate("/conditions", method="put", conditions=conditions(["진행"], requiredRoles=["진행"]))
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(self.room().agent_input_revision, before.agent_input_revision + 1)

    def test_agent_final_result_makes_the_room_immutable_like_a_v1_final(self) -> None:
        self.make_potato()
        self.add_final_agent_run(round_=0)
        put = self.mutate("/conditions", method="put", conditions=conditions(["진행"], requiredRoles=["진행"]))
        self.assertEqual((put.status_code, put.json()["detail"]), (409, "이미 최종 확정된 모임입니다."))
        self.assertEqual(self.client.get("/v1/meetings/" + self.id, headers=self.headers(self.host)).status_code, 200)

    def test_a_final_result_of_an_earlier_coordination_round_does_not_block_v1_inputs(self) -> None:
        self.make_potato()
        self.add_final_agent_run(round_=0)
        with session() as db, db.begin():
            db.get(Room, self.id).coordination_round = 1
        put = self.mutate("/conditions", method="put", conditions=conditions(["진행"], requiredRoles=["진행"]))
        self.assertEqual(put.status_code, 200, put.text)

    def test_v1_role_round_changes_do_not_move_the_coordination_round(self) -> None:
        self.add_final_agent_run(round_=0)  # a plain /v1 room, only the Agent record exists
        with session() as db, db.begin():
            db.get(Room, self.id).current_round = 9  # as if /v1 had recalculated
        with session() as db:
            room = db.get(Room, self.id)
            self.assertEqual((room.current_round, room.coordination_round), (9, 0))
            final = db.scalar(select(AgentRun).where(AgentRun.room_id == self.id, AgentRun.finalized_room_round == room.coordination_round))
            self.assertIsNotNone(final)


if __name__ == "__main__":
    unittest.main()
