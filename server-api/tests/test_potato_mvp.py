"""4-person MVP path: DB identity, leave, room list, and the leave/RSVP boundary."""
from __future__ import annotations

import unittest

from db_v21.models.account import Account
from db_v21.models.agent import RoomInvitation
from db_v21.models.room import Room, RoomMember
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests import test_potato_meet as tpm

database_module = tpm.database_module
NAMES = {"host": "방장", "a": "민수", "b": "지훈", "c": "영희"}


class FourPersonTests(tpm.PotatoBase):
    def start_four(self):
        self.create_room(minimumAttendeeCount=2, nickname=NAMES["host"])
        for key in ("a", "b", "c"):
            self.assertEqual(self.join(key, NAMES[key]).status_code, 200)

    def test_four_real_accounts_and_per_room_names_in_the_database(self) -> None:
        self.start_four()
        with Session(database_module.engine()) as db:
            members = list(db.scalars(select(RoomMember).where(RoomMember.room_id == self.rid)))
            accounts = {a.id: a for a in db.scalars(select(Account).where(
                Account.id.in_([m.account_id for m in members])))}
        self.assertEqual(len(members), 4)
        self.assertEqual(len({m.account_id for m in members}), 4)  # four distinct accounts
        self.assertEqual(sorted(m.nickname for m in members), sorted(NAMES.values()))
        self.assertTrue(all(accounts[m.account_id].account_type == "USER" for m in members))
        self.assertEqual([m.room_role for m in members].count("OWNER"), 1)

        listed = self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
        self.assertEqual(sorted(p["displayName"] for p in listed), sorted(NAMES.values()))
        self.assertEqual(len({p["participantId"] for p in listed}), 4)
        for key in NAMES:  # the same person may use another name in another room
            self.assertEqual(self.client.get(f"/v2/rooms/{self.rid}", headers=self.h(key)).json()["me"]["accountId"],
                             self.user(key)["accountId"])

    def test_display_name_is_per_room(self) -> None:
        self.start_four()
        self.create_room(key="second", nickname="다른방장", title="두번째")
        self.assertEqual(self.join("a", "민수-두번째").status_code, 200)
        names = {r["roomId"]: r["myNickname"]
                 for r in self.client.get("/v2/rooms", headers=self.h("a")).json()["rooms"]}
        self.assertEqual(sorted(names.values()), ["민수", "민수-두번째"])

    def test_four_people_to_candidates(self) -> None:
        self.start_four()
        for key, (start, end) in {"host": (540, 720), "a": (600, 780), "b": (630, 800), "c": (660, 900)}.items():
            self.assertEqual(self.submit(key, [tpm.slot(start=start, end=end)]).status_code, 200)
        run = self.start_run()
        self.assertEqual(run.status_code, 202, run.text)
        self.assertEqual(self.work().status, "ALL_AVAILABLE")
        candidates = self.client.get(
            f"/v2/rooms/{self.rid}/agent-runs/{run.json()['runId']}/candidates", headers=self.h("host")
        ).json()["candidates"]
        self.assertEqual(len(candidates[0]["members"]), 4)
        self.assertEqual(candidates[0]["startsAt"][11:16], "11:00")  # the 4-way overlap starts at 11:00


class RoomListTests(tpm.PotatoBase):
    def test_home_lists_only_my_potato_rooms(self) -> None:
        self.create_room()
        self.join("a", "민수")
        mine = self.client.get("/v2/rooms", headers=self.h("a")).json()["rooms"]
        self.assertEqual([(r["roomId"], r["role"], r["finalized"]) for r in mine], [(self.rid, "invitee", False)])
        self.assertEqual(mine[0]["code"], self.room["code"])
        self.assertEqual(self.client.get("/v2/rooms", headers=self.h("stranger")).json()["rooms"], [])
        self.assertEqual(self.client.get("/v2/rooms").status_code, 401)
        self.assertEqual(self.client.get("/v2/rooms", params={"limit": 0}, headers=self.h("a")).status_code, 422)


class LeaveTests(tpm.PotatoBase):
    def setUp(self) -> None:
        super().setUp()
        self.create_room()
        self.join("a", "민수")
        self.join("b", "지훈")

    def test_code_joiner_can_leave_and_history_is_kept(self) -> None:
        self.submit("a", [tpm.slot()])
        self.submit("host", [tpm.slot()])
        run_id = self.start_run().json()["runId"]
        revision = self.room_row().agent_input_revision
        left = self.client.post(f"/v2/rooms/{self.rid}/leave", headers=self.h("a"))
        self.assertEqual((left.status_code, left.json()["left"], left.json()["replayed"]), (200, True, False))
        self.assertEqual(self.room_row().agent_input_revision, revision + 1)
        self.assertEqual(self.run_row(run_id).status, "STALE")  # the open Run no longer matches
        with Session(database_module.engine()) as db:
            member = db.scalar(select(RoomMember).where(RoomMember.room_id == self.rid, RoomMember.nickname == "민수"))
            self.assertEqual(member.membership_status, "LEFT")  # soft: the row and submissions remain
        again = self.client.post(f"/v2/rooms/{self.rid}/leave", headers=self.h("a"))
        self.assertTrue(again.json()["replayed"])
        self.assertEqual(self.room_row().agent_input_revision, revision + 1)
        self.assertEqual(self.client.get(f"/v2/rooms/{self.rid}", headers=self.h("a")).status_code, 403)
        self.assertEqual(self.client.get("/v2/rooms", headers=self.h("a")).json()["rooms"], [])
        rejoin = self.join("a", "민수")  # re-joining is not defined yet
        self.assertEqual((rejoin.status_code, rejoin.json()["detail"]["code"]), (409, "MEMBERSHIP_INACTIVE"))

    def test_leaving_never_changes_anyone_elses_rsvp_and_nobody_is_absent(self) -> None:
        self.client.post(f"/v2/rooms/{self.rid}/leave", headers=self.h("a"))
        listed = self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
        self.assertEqual(sorted(p["displayName"] for p in listed), ["방장", "지훈"])
        self.assertTrue(all(p["participationStatus"] == "accepted" for p in listed))

    def test_host_and_non_members_cannot_leave(self) -> None:
        host = self.client.post(f"/v2/rooms/{self.rid}/leave", headers=self.h("host"))
        self.assertEqual((host.status_code, host.json()["detail"]["code"]), (409, "HOST_CANNOT_LEAVE"))
        self.assertEqual(self.client.post(f"/v2/rooms/{self.rid}/leave", headers=self.h("stranger")).status_code, 404)
        self.assertEqual(self.client.post(f"/v2/rooms/{self.rid}/leave").status_code, 401)

    def test_invited_member_cannot_leave_because_the_snapshot_would_reject_the_room(self) -> None:
        invitee = self.user("inv")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.client.put(f"/v2/rooms/{self.rid}/invitations/me",
                        json={"response": "ACCEPTED", "nickname": "초대"}, headers=self.h("inv"))
        blocked = self.client.post(f"/v2/rooms/{self.rid}/leave", headers=self.h("inv"))
        self.assertEqual((blocked.status_code, blocked.json()["detail"]["code"]), (409, "LEAVE_NOT_SUPPORTED_FOR_INVITED"))
        # characterization: this is what a leave would do to the snapshot builder
        with Session(database_module.engine()) as db, db.begin():
            member = db.scalar(select(RoomMember).where(RoomMember.nickname == "초대"))
            member.membership_status = "LEFT"
        self.submit("host", [tpm.slot()])
        broken = self.start_run()
        self.assertEqual((broken.status_code, broken.json()["detail"]["code"]), (422, "INVALID_MEETING_SNAPSHOT"))
        with Session(database_module.engine()) as db:
            invitation = db.scalar(select(RoomInvitation).where(RoomInvitation.account_id == invitee))
            self.assertEqual(invitation.response_status, "ACCEPTED")  # RSVP untouched


if __name__ == "__main__":
    unittest.main()


class CommitBeforeResponseTests(unittest.TestCase):
    """A yield-dependency session normally commits AFTER the response is sent, so a
    client that logs in right after registering can still see nothing (observed on
    PostgreSQL). The Potato path must commit first: scope="function"."""

    def test_auth_and_run_endpoints_commit_before_responding(self) -> None:
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        for name in ("user_auth.py", "agent_routes.py"):
            source = (root / name).read_text(encoding="utf-8")
            self.assertNotIn("Depends(db_session)", source, name)
            self.assertIn('Depends(db_session, scope="function")', source, name)


class LatestRunTests(tpm.PotatoBase):
    def test_every_participant_follows_the_same_latest_run(self) -> None:
        self.create_room()
        self.join("a", "민수")
        url = f"/v2/rooms/{self.rid}/latest-run"
        none = self.client.get(url, headers=self.h("a")).json()
        self.assertEqual(none["run"], None)
        self.submit("host", [tpm.slot()])
        self.submit("a", [tpm.slot()])
        started = self.start_run().json()["runId"]
        for who in ("host", "a"):
            run = self.client.get(url, headers=self.h(who)).json()["run"]
            self.assertEqual((run["runId"], run["current"], run["finalized"]), (started, True, False))
        self.submit("a", [tpm.slot(start=700, end=800)])  # input changes -> that Run is stale
        run = self.client.get(url, headers=self.h("a")).json()["run"]
        self.assertEqual((run["runId"], run["status"], run["current"]), (started, "STALE", False))
        second = self.start_run("run-2").json()["runId"]
        self.assertEqual(self.client.get(url, headers=self.h("host")).json()["run"]["runId"], second)
        self.assertEqual(self.client.get(url, headers=self.h("stranger")).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 401)
