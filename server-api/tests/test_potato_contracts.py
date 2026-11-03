"""Characterization tests: where the entry API meets the existing Agent policy.

These pin CURRENT behavior that constrains pending product decisions
(explicit "no availability", date change for a new round). If a decision
changes the Agent contract these tests are the checklist of what must move.
"""
from __future__ import annotations

import unittest

from db_v21.base import now
from db_v21.models.condition import ConditionSubmission
from db_v21.models.room import Room, RoomMember
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests import test_potato_meet as tpm

database_module = tpm.database_module


class NoAvailabilityContractTests(tpm.PotatoBase):
    """DOMAIN_POLICY: a submitted empty slot list is invalid; explicit
    unavailability must be a separate constraint (not yet defined)."""

    def setUp(self) -> None:
        super().setUp()
        self.create_room()
        self.join("a", "민수")
        self.submit("host", [tpm.slot()])

    def test_the_api_refuses_an_empty_submission(self) -> None:
        self.assertEqual(self.submit("a", []).status_code, 422)
        got = self.client.get(f"/v2/rooms/{self.rid}/availability/me", headers=self.h("a")).json()
        self.assertEqual(got["status"], "not_submitted")  # nothing was recorded

    def test_an_empty_submission_row_would_make_every_run_fail_so_it_must_never_exist(self) -> None:
        with Session(database_module.engine()) as db, db.begin():
            member = db.scalar(select(RoomMember).where(
                RoomMember.room_id == self.rid, RoomMember.nickname == "민수"))
            db.add(ConditionSubmission(room_member_id=member.id, version=1, confirmed={}, submitted_at=now()))
        started = self.start_run()
        self.assertEqual((started.status_code, started.json()["detail"]["code"]), (422, "INVALID_MEETING_SNAPSHOT"))

    def test_a_decline_is_the_existing_way_to_say_i_cannot_come_and_it_is_not_unavailability(self) -> None:
        invitee = self.user("b")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.submit("a", [tpm.slot()])
        self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "DECLINED"}, headers=self.h("b"))
        run_id = self.start_run().json()["runId"]
        self.assertEqual(self.work().status, "ALL_AVAILABLE")  # D-04: decliner is simply not on the roster
        candidate = self.client.get(
            f"/v2/rooms/{self.rid}/agent-runs/{run_id}/candidates", headers=self.h("host")
        ).json()["candidates"][0]
        self.assertEqual(len(candidate["members"]), 2)
        self.assertTrue(all(m["participationStatus"] == "ATTENDING" for m in candidate["members"]))

    def test_an_accepted_invitee_cannot_withdraw_so_there_is_no_way_out_for_someone_with_no_time(self) -> None:
        invitee = self.user("b")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "ACCEPTED", "nickname": "철수"}, headers=self.h("b"))
        out = self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "DECLINED"}, headers=self.h("b"))
        self.assertEqual((out.status_code, out.json()["detail"]["code"]), (409, "INVITATION_ALREADY_ACCEPTED"))
        # ...and the Run then waits for that person's availability instead of guessing it
        self.submit("a", [tpm.slot()])
        self.start_run()
        self.assertEqual(self.work().status, "WAITING_FOR_INPUT")


class DateChangeContractTests(tpm.PotatoBase):
    """A new round that replaced coordination.dates would orphan existing slots."""

    def test_changing_the_configured_dates_breaks_snapshots_that_hold_old_availability(self) -> None:
        self.create_room()
        self.join("a", "민수")
        self.submit("host", [tpm.slot()])
        self.submit("a", [tpm.slot()])
        with Session(database_module.engine()) as db, db.begin():
            room = db.get(Room, self.rid)
            settings = dict(room.meeting_settings)
            settings["coordination"] = {**settings["coordination"], "dates": ["2030-02-01"], "excludedDates": []}
            room.meeting_settings = settings
            room.agent_input_revision += 1
        broken = self.start_run()
        self.assertEqual((broken.status_code, broken.json()["detail"]["code"]), (422, "INVALID_MEETING_SNAPSHOT"))


if __name__ == "__main__":
    unittest.main()
