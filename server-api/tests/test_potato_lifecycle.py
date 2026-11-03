"""Lifecycle (cycle close) uses coordination dates for Potato Meet rooms."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from admin import lifecycle
from db_v21.models.room import Room
from services.meeting_domain import is_potato_meet, potato_deadline
from services.meeting_snapshot import build_meeting_snapshot
from sqlalchemy.orm import Session
from tests import test_potato_meet as tpm
from tests.test_agent_consistency import ConsistencyBase

database_module = tpm.database_module


class PotatoLifecycleTests(tpm.PotatoBase):
    def snapshot_hash(self):
        with Session(database_module.engine()) as db:
            return build_meeting_snapshot(
                db, room_id=self.rid, agent_session_id="s", run_id="r", consent_round=1
            ).input_snapshot_hash

    def test_deadline_uses_the_active_coordination_dates(self) -> None:
        self.create_room()
        with Session(database_module.engine()) as db:
            room = db.get(Room, self.rid)
            scheduled, actual = potato_deadline(db, room)
            self.assertEqual((scheduled, actual), (tpm.D2, None))
            _, cutoff = lifecycle.deadline(db, room)
        self.assertEqual(cutoff, datetime(2030, 1, 11, 15, 0, tzinfo=timezone.utc))  # 01-12 00:00 KST
        with Session(database_module.engine()) as db, db.begin():
            room = db.get(Room, self.rid)
            settings = dict(room.meeting_settings)
            settings["coordination"] = {**settings["coordination"], "excludedDates": [tpm.D2]}
            room.meeting_settings = settings
        with Session(database_module.engine()) as db:
            self.assertEqual(potato_deadline(db, db.get(Room, self.rid))[0], tpm.D1)

    def test_v1_rooms_keep_their_own_deadline_rule(self) -> None:
        client = self.client
        host = client.post("/v1/meetings", json={
            "title": "v1", "name": "방장", "dates": ["2030-03-03"], "roles": ["진행"],
            "roleNeeds": {"진행": 1}, "duration": 60, "windowStart": 540, "windowEnd": 720}).json()
        with Session(database_module.engine()) as db:
            room = db.get(Room, host["meeting"]["id"])
            self.assertFalse(is_potato_meet(room))
            self.assertEqual(lifecycle.deadline(db, room)[0], "2030-03-03")

    def test_admin_lifecycle_keeps_a_new_potato_room_active_and_closes_it_after_its_dates(self) -> None:
        with patch("admin.lifecycle.enabled", return_value=True), patch("admin.security.enabled", return_value=True):
            self.create_room()
            self.assertEqual(self.join("a", "민수").status_code, 200)  # snapshots need 2 eligible people
            before = self.snapshot_hash()
            got = self.client.get(f"/v2/rooms/{self.rid}", headers=self.h("host"))
            self.assertEqual(got.status_code, 200, got.text)
            with Session(database_module.engine()) as db, db.begin():
                self.assertEqual(lifecycle.ensure(db, db.get(Room, self.rid)).state, "ACTIVE")
            self.assertEqual(before, self.snapshot_hash())  # lifecycle metadata never touches the input hash
            self.assertEqual(self.submit("host", [tpm.slot()]).status_code, 200)  # not expired at birth

            after_dates = datetime(2030, 2, 1, tzinfo=timezone.utc)
            with patch("admin.lifecycle.now", return_value=after_dates):
                self.assertEqual(self.client.get(f"/v2/rooms/{self.rid}", headers=self.h("host")).status_code, 200)
                closed = self.submit("host", [tpm.slot(start=100, end=200)])
                self.assertEqual(closed.status_code, 409)  # the closed cycle is read-only
                self.assertEqual(self.client.put(f"/v2/rooms/{self.rid}/minimum-attendees",
                                                 json={"minimumAttendeeCount": 2}, headers=self.h("host")).status_code, 200)  # unchanged value = replay


class FinalizedDeadlineTests(ConsistencyBase):
    def test_final_result_decides_when_the_cycle_closes(self) -> None:
        with Session(self.engine) as db:
            scheduled, actual = potato_deadline(db, db.get(Room, "room-1"))
        self.assertEqual((scheduled, actual), ("2026-11-05", None))
        self.finalize_run()
        with Session(self.engine) as db:
            scheduled, actual = potato_deadline(db, db.get(Room, "room-1"))
            _, cutoff = lifecycle.deadline(db, db.get(Room, "room-1"))
        self.assertEqual(scheduled, "2026-11-05")
        self.assertIsNotNone(actual.tzinfo)
        self.assertEqual((actual.hour, actual.minute), (10, 0))  # candidate 09:00-10:00 KST
        self.assertEqual(cutoff, datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
