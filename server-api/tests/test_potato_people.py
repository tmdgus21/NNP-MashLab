"""Invite-candidate lookup, join path contract, exclusion audit, lifecycle guard."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from db_v21.models.admin import AdminAuditLog
from services import coordination_round as cr
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests import test_potato_meet as tpm
from tests.test_agent_consistency import ConsistencyBase

database_module = tpm.database_module


class RecentPeopleTests(tpm.PotatoBase):
    def people(self, who="host", **params):
        r = self.client.get("/v2/people/recent", params=params, headers=self.h(who))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["people"]

    def setUp(self) -> None:
        super().setUp()
        self.create_room()
        self.room1 = self.rid
        self.join("a", "민수")
        self.join("b", "Chris")

    def test_lists_only_people_from_shared_rooms_and_never_self(self) -> None:
        people = self.people()
        self.assertEqual(sorted(p["nickname"] for p in people), ["Chris", "민수"])
        self.assertTrue(all(p["sharedRoomCount"] == 1 for p in people))
        self.assertNotIn(self.user("host")["accountId"], [p["accountId"] for p in people])
        self.assertEqual(self.people("stranger"), [])  # no shared room -> nothing, no directory
        self.assertEqual(self.client.get("/v2/people/recent").status_code, 401)

    def test_search_filters_the_callers_own_contacts_only(self) -> None:
        self.assertEqual([p["nickname"] for p in self.people(q="민")], ["민수"])
        self.assertEqual([p["nickname"] for p in self.people(q="CHRIS")], ["Chris"])  # case-insensitive
        self.assertEqual(self.people(q="없는사람"), [])
        limit_zero = self.client.get("/v2/people/recent", params={"limit": 0}, headers=self.h("host"))
        self.assertEqual(limit_zero.status_code, 422)

    def test_shared_room_count_and_room_annotation(self) -> None:
        self.create_room(key="second", nickname="방장2", title="두번째")
        second = self.rid
        self.join("a", "민수2")
        by_name = {p["nickname"]: p for p in self.people()}
        self.assertEqual(by_name["민수2"]["sharedRoomCount"], 2)  # latest nickname wins, both rooms counted
        a, b = self.user("a")["accountId"], self.user("b")["accountId"]
        annotated = {p["accountId"]: p["inRoom"] for p in self.people(roomId=second)}
        self.assertEqual((annotated[a], annotated[b]), ("member", None))
        self.client.post(f"/v2/rooms/{second}/invitations", json={"accountIds": [b]}, headers=self.h("host"))
        self.assertEqual({p["accountId"]: p["inRoom"] for p in self.people(roomId=second)}[b], "pending")
        self.client.put(f"/v2/rooms/{second}/invitations/me", json={"response": "DECLINED"}, headers=self.h("b"))
        self.assertEqual({p["accountId"]: p["inRoom"] for p in self.people(roomId=second)}[b], "declined")
        outsider = self.client.get("/v2/people/recent", params={"roomId": second}, headers=self.h("stranger"))
        self.assertEqual(outsider.status_code, 403)

    def test_picking_a_person_replaces_knowing_the_account_id(self) -> None:
        self.create_room(key="third", nickname="방장3", title="세번째")
        third = self.rid
        pick = next(p for p in self.people() if p["nickname"] == "Chris")
        r = self.client.post(
            f"/v2/rooms/{third}/invitations", json={"accountIds": [pick["accountId"]]}, headers=self.h("host")
        )
        self.assertEqual(r.json()["results"][0]["result"], "sent")


class JoinPathTests(tpm.PotatoBase):
    def test_participants_expose_how_each_person_joined(self) -> None:
        self.create_room()
        self.join("code", "코드참가")
        invitee = self.user("inv")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        pending = self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
        paths = {p["displayName"] or "(pending)": p["joinPath"] for p in pending}
        self.assertEqual(paths, {"방장": "organizer", "코드참가": "code", "(pending)": "invitation"})
        code = next(p for p in pending if p["joinPath"] == "code")
        # the truthful server state that the mobile type must be able to represent
        self.assertEqual(
            (code["role"], code["invitationStatus"], code["participationStatus"]),
            ("invitee", "not_sent", "accepted"),
        )
        self.client.put(
            f"/v2/rooms/{self.rid}/invitations/me",
            json={"response": "ACCEPTED", "nickname": "초대참가"}, headers=self.h("inv"),
        )
        later = self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
        invited = next(p for p in later if p["displayName"] == "초대참가")
        self.assertEqual(
            (invited["joinPath"], invited["invitationStatus"], invited["participationStatus"]),
            ("invitation", "sent", "accepted"),
        )


class ExclusionAuditTests(tpm.PotatoBase):
    def audit_rows(self):
        with Session(database_module.engine()) as db:
            return list(db.scalars(select(AdminAuditLog).where(AdminAuditLog.action_type == "room.exclude_invitee")))

    def test_exclusion_is_audited_with_actor_invitee_and_reason(self) -> None:
        self.enable_exclusion()
        self.create_room()
        invitee = self.user("b")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        body = {"accountId": invitee, "reason": "연락 안 됨"}
        self.client.post(f"/v2/rooms/{self.rid}/invitations/exclude", json=body, headers=self.h("host"))
        rows = self.audit_rows()
        self.assertEqual(len(rows), 1)
        for expected in (invitee, self.user("host")["accountId"], "연락 안 됨"):
            self.assertIn(expected, rows[0].reason)
        self.client.post(f"/v2/rooms/{self.rid}/invitations/exclude", json=body, headers=self.h("host"))  # replay
        self.assertEqual(len(self.audit_rows()), 1)  # a replay is not audited twice


class RoundVsLifecycleTests(ConsistencyBase):
    def open_round(self):
        return cr.open_next_coordination_round(
            self.factory, room_id="room-1", actor_account_id="account-host",
            idempotency_key="k", expected_round=0,
        )

    def test_a_closed_cycle_refuses_a_new_round_before_changing_anything(self) -> None:
        self.finalize_run()
        before_room, before_run = self.room(), self._row(self.run_id)
        after_close = datetime(2027, 1, 1, tzinfo=timezone.utc)
        with patch("admin.lifecycle.enabled", return_value=True), patch(
            "admin.lifecycle.now", return_value=after_close
        ):
            with self.assertRaises(Exception) as raised:
                self.open_round()
        self.assertEqual(getattr(raised.exception, "status_code", None), 409)
        room = self.room()
        self.assertEqual(
            (room.coordination_round, room.agent_input_revision, room.revision),
            (before_room.coordination_round, before_room.agent_input_revision, before_room.revision),
        )
        self.assertEqual(self._row(self.run_id).finalized_at, before_run.finalized_at)

    def test_an_active_cycle_still_opens_a_round(self) -> None:
        self.finalize_run()
        before_close = datetime(2026, 11, 3, tzinfo=timezone.utc)
        with patch("admin.lifecycle.enabled", return_value=True), patch(
            "admin.lifecycle.now", return_value=before_close
        ):
            opening = self.open_round()
        self.assertEqual((opening.to_round, opening.changed), (1, True))


if __name__ == "__main__":
    unittest.main()
