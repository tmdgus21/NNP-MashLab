"""Potato Meet entry flow over HTTP: create -> join/invite/RSVP -> availability -> Agent."""
from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module  # noqa: E402

database_module._engine = None

from database import initialize  # noqa: E402
from db_v21.models.agent import AgentRun, RoomInvitation  # noqa: E402
from db_v21.models.room import Room, RoomMember  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from services import potato_meet  # noqa: E402
from services.agent_worker import claim_next_agent_run, execute_agent_run  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

TODAY = date(2029, 12, 31)
D1, D2 = "2030-01-10", "2030-01-11"


def slot(day=D1, start=540, end=660):
    return {"date": day, "startTimeMinutes": start, "endTimeMinutes": end}


class PotatoBase(unittest.TestCase):
    def setUp(self) -> None:
        database_module._engine = None
        initialize()
        self.client = TestClient(app)
        for target in ("services.potato_meet._today",):
            patcher = patch(target, lambda: TODAY)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.users: dict[str, dict] = {}
        self.n = 0

    # -- helpers
    def user(self, name: str) -> dict:
        if name not in self.users:
            self.n += 1
            body = self.client.post("/v1/auth/register", json={
                "email": f"{name}{self.n}@example.test", "password": "password-1234567"}).json()
            self.users[name] = body
        return self.users[name]

    def h(self, name, key=None):
        headers = {"Authorization": "Bearer " + self.user(name)["token"]}
        if key:
            headers["Idempotency-Key"] = key
        return headers

    def create_body(self, **over):
        body = {"title": "금요 저녁", "activity": "식사", "location": "강남역",
                "durationMinutes": 60, "dates": [D1, D2], "minimumAttendeeCount": 2,
                "nickname": "방장"}
        body.update(over)
        return body

    def create_room(self, key="create-1", **over):
        r = self.client.post("/v2/rooms", json=self.create_body(**over), headers=self.h("host", key))
        self.assertIn(r.status_code, (200, 201), r.text)
        self.room = r.json()
        self.rid = self.room["roomId"]
        return self.room

    def join(self, name, nickname):
        return self.client.post("/v2/rooms/join", json={"code": self.room["code"], "nickname": nickname},
                                headers=self.h(name))

    def submit(self, name, slots, **extra):
        return self.client.put(f"/v2/rooms/{self.rid}/availability/me",
                               json={"timeSlots": slots, **extra}, headers=self.h(name))

    def enable_exclusion(self) -> None:
        """Release builds keep host exclusion off (no RSVP deadline exists yet)."""
        patcher = patch.dict(os.environ, {"POTATO_ALLOW_UNGATED_EXCLUSION": "1"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def room_row(self) -> Room:
        with Session(database_module.engine()) as db:
            room = db.get(Room, self.rid)
            db.expunge(room)
            return room

    def run_row(self, run_id) -> AgentRun:
        with Session(database_module.engine()) as db:
            row = db.get(AgentRun, run_id)
            db.expunge(row)
            return row

    def start_run(self, key="run-1"):
        return self.client.post(
            f"/v2/rooms/{self.rid}/agent-runs",
            json={"expectedInputRevision": self.room_row().agent_input_revision},
            headers=self.h("host", key),
        )

    def work(self):
        factory = lambda: Session(database_module.engine())  # noqa: E731
        claim = claim_next_agent_run(factory, worker_id="w", lease_seconds=30)
        return execute_agent_run(claim, factory, lease_seconds=30)


class CreateRoomTests(PotatoBase):
    def test_create_stores_a_server_validated_coordination_block(self) -> None:
        view = self.create_room()
        self.assertEqual(
            (view["title"], view["activity"], view["durationMinutes"], view["dates"],
             view["minimumAttendeeCount"], view["me"]["role"], view["coordinationRound"],
             view["agentInputRevision"], view["eligibleParticipantCount"]),
            ("금요 저녁", "식사", 60, [D1, D2], 2, "organizer", 0, 1, 1),
        )
        self.assertEqual(len(view["code"]), 8)
        room = self.room_row()
        self.assertEqual(room.meeting_settings["coordination"]["schemaVersion"], 1)
        self.assertNotIn("roles", room.meeting_settings)  # no /v1 role-assignment policy
        self.assertEqual(room.progress_status, "collecting")

    def test_idempotent_create_and_key_reuse(self) -> None:
        first = self.create_room()
        again = self.client.post("/v2/rooms", json=self.create_body(), headers=self.h("host", "create-1"))
        self.assertEqual((again.status_code, again.json()["roomId"], again.json()["replayed"]),
                         (200, first["roomId"], True))
        other = self.client.post("/v2/rooms", json=self.create_body(title="다른"), headers=self.h("host", "create-1"))
        self.assertEqual((other.status_code, other.json()["detail"]["code"]), (409, "IDEMPOTENCY_KEY_REUSED"))
        with Session(database_module.engine()) as db:
            self.assertEqual(len(list(db.scalars(select(Room).where(Room.created_by_account_id == self.user("host")["accountId"])))), 1)

    def test_validation_and_auth(self) -> None:
        self.assertEqual(self.client.post("/v2/rooms", json=self.create_body()).status_code, 401)
        no_key = self.client.post("/v2/rooms", json=self.create_body(), headers=self.h("host"))
        self.assertEqual((no_key.status_code, no_key.json()["detail"]["code"]), (400, "IDEMPOTENCY_KEY_REQUIRED"))
        bad = [
            dict(minimumAttendeeCount=1), dict(durationMinutes=0), dict(durationMinutes=1441),
            dict(dates=[]), dict(title=" "), dict(timeZone="UTC"), dict(extra=1),
            dict(durationMinutes=60.5), dict(nickname="x" * 31), dict(dates=["2029-12-30"]),
        ]
        for index, over in enumerate(bad):
            r = self.client.post("/v2/rooms", json=self.create_body(**over), headers=self.h("host", f"bad-{index}"))
            self.assertEqual(r.status_code, 422, (over, r.text))

    def test_get_room_requires_membership(self) -> None:
        self.create_room()
        self.assertEqual(self.client.get(f"/v2/rooms/{self.rid}", headers=self.h("host")).status_code, 200)
        self.assertEqual(self.client.get(f"/v2/rooms/{self.rid}", headers=self.h("stranger")).status_code, 403)


class JoinInviteTests(PotatoBase):
    def test_link_join_is_acceptance_and_changes_agent_input(self) -> None:
        self.create_room()
        before = self.room_row().agent_input_revision
        r = self.join("a", "민수")
        self.assertEqual((r.status_code, r.json()["me"]["role"], r.json()["eligibleParticipantCount"]), (200, "invitee", 2))
        self.assertEqual(self.room_row().agent_input_revision, before + 1)
        again = self.join("a", "다른이름")  # replay: nothing changes
        self.assertEqual((again.status_code, again.json()["replayed"]), (200, True))
        self.assertEqual(self.room_row().agent_input_revision, before + 1)
        participants = self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
        guest = next(p for p in participants if p["displayName"] == "민수")
        self.assertEqual((guest["role"], guest["invitationStatus"], guest["participationStatus"],
                          guest["availability"]["status"]), ("invitee", "not_sent", "accepted", "not_submitted"))

    def test_join_errors(self) -> None:
        self.create_room()
        self.assertEqual(self.client.post("/v2/rooms/join", json={"code": "ZZZZZZZZ", "nickname": "x"},
                                          headers=self.h("a")).status_code, 404)
        self.assertEqual(self.join("a", "방장").status_code, 409)  # nickname already taken by the host
        self.assertEqual(self.client.post("/v2/rooms/join", json={"code": self.room["code"], "nickname": "x"}).status_code, 401)

    def test_invitation_rsvp_and_availability_are_three_separate_facts(self) -> None:
        self.create_room()
        invitee = self.user("b")["accountId"]
        self.user("c")
        r = self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.assertEqual((r.status_code, r.json()["results"]), (200, [{"accountId": invitee, "result": "sent"}]))
        again = self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.assertEqual(again.json()["results"][0]["result"], "unchanged")

        pending = next(p for p in self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
                       if p["participantId"] == invitee)
        self.assertEqual((pending["invitationStatus"], pending["participationStatus"], pending["availability"]["status"], pending["memberId"]),
                         ("sent", "pending", "not_submitted", None))  # not an absence, not a decline
        mine = self.client.get("/v2/room-invitations/me", headers=self.h("b")).json()["invitations"]
        self.assertEqual((mine[0]["roomId"], mine[0]["participationStatus"]), (self.rid, "pending"))

        self.assertEqual(self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "ACCEPTED"}, headers=self.h("b")).status_code, 422)
        accepted = self.client.put(f"/v2/rooms/{self.rid}/invitations/me",
                                   json={"response": "ACCEPTED", "nickname": "철수"}, headers=self.h("b"))
        self.assertEqual((accepted.status_code, accepted.json()["eligibleParticipantCount"]), (200, 2))
        accepted_again = self.client.put(f"/v2/rooms/{self.rid}/invitations/me",
                                         json={"response": "ACCEPTED", "nickname": "철수"}, headers=self.h("b"))
        self.assertTrue(accepted_again.json()["replayed"])
        declined = self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "DECLINED"}, headers=self.h("b"))
        self.assertEqual((declined.status_code, declined.json()["detail"]["code"]), (409, "INVITATION_ALREADY_ACCEPTED"))

    def test_decline_then_accept_and_authorization(self) -> None:
        self.create_room()
        invitee = self.user("b")["accountId"]
        self.assertEqual(self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("b")).status_code, 403)
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        d = self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "DECLINED"}, headers=self.h("b"))
        self.assertEqual(d.status_code, 200)
        listed = next(p for p in self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
                      if p["participantId"] == invitee)
        self.assertEqual(listed["participationStatus"], "declined")
        a = self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "ACCEPTED", "nickname": "철수"}, headers=self.h("b"))
        self.assertEqual(a.status_code, 200)
        # unknown accounts and uninvited responders
        self.assertEqual(self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": ["nope"]}, headers=self.h("host")).json()["detail"]["code"], "UNKNOWN_ACCOUNT")
        self.assertEqual(self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "ACCEPTED", "nickname": "z"}, headers=self.h("stranger")).status_code, 404)

    def test_not_sent_invitation_cannot_be_answered_but_can_be_sent_later(self) -> None:
        self.create_room()
        invitee = self.user("b")["accountId"]
        r = self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee], "send": False}, headers=self.h("host"))
        self.assertEqual(r.json()["results"][0]["result"], "created")
        blocked = self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "DECLINED"}, headers=self.h("b"))
        self.assertEqual(blocked.json()["detail"]["code"], "INVITATION_NOT_SENT")
        sent = self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.assertEqual(sent.json()["results"][0]["result"], "sent")

    def test_excluded_invitation_cannot_join_or_answer(self) -> None:
        self.create_room()
        invitee = self.user("b")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        with Session(database_module.engine()) as db:
            row = db.scalar(select(RoomInvitation).where(RoomInvitation.account_id == invitee))
            host = db.scalar(select(RoomMember).where(RoomMember.room_id == self.rid))
            from db_v21.base import now

            row.eligibility_status, row.excluded_at = "EXCLUDED_BY_HOST", now()
            row.excluded_by_member_id, row.exclusion_reason = host.id, "test"
            db.commit()
        self.assertEqual(self.join("b", "철수").status_code, 403)
        self.assertEqual(self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "ACCEPTED", "nickname": "철수"}, headers=self.h("b")).status_code, 403)


class AvailabilityTests(PotatoBase):
    def setUp(self) -> None:
        super().setUp()
        self.create_room()
        self.join("a", "민수")

    def test_submit_versions_normalize_and_replay(self) -> None:
        r = self.submit("a", [slot(start=540, end=600), slot(start=600, end=660), slot(start=630, end=720), slot(D2, 0, 1440)])
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["timeSlots"], [slot(D1, 540, 720), slot(D2, 0, 1440)])  # touching + overlapping merged
        revision = self.room_row().agent_input_revision
        same = self.submit("a", [slot(D2, 0, 1440), slot(D1, 540, 720)])  # same content, other order
        self.assertEqual((same.json()["version"], same.json()["changed"]), (1, False))
        self.assertEqual(self.room_row().agent_input_revision, revision)  # a retry is not an input change
        changed = self.submit("a", [slot(D1, 540, 700)], expectedVersion=1)
        self.assertEqual((changed.json()["version"], changed.json()["changed"]), (2, True))
        self.assertEqual(self.room_row().agent_input_revision, revision + 1)
        got = self.client.get(f"/v2/rooms/{self.rid}/availability/me", headers=self.h("a")).json()
        self.assertEqual((got["status"], got["version"], got["timeSlots"]), ("submitted", 2, [slot(D1, 540, 700)]))

    def test_version_conflict_between_devices(self) -> None:
        self.submit("a", [slot()])
        conflict = self.submit("a", [slot(start=100, end=200)], expectedVersion=0)
        self.assertEqual((conflict.status_code, conflict.json()["detail"]["code"]), (409, "SUBMISSION_VERSION_CONFLICT"))

    def test_rules_one_minute_precision_dates_and_limits(self) -> None:
        empty = self.submit("a", [])
        self.assertEqual((empty.status_code, empty.json()["detail"]["code"]), (422, "AVAILABILITY_EMPTY"))
        bad = [
            [slot(start=540.5, end=660)], [slot(start=660, end=660)], [slot(start=700, end=600)],
            [slot(start=-1, end=60)], [slot(start=0, end=1441)], [slot("2030-01-12")], [slot("2029-12-30")],
            [slot()] * 201,
        ]
        for slots in bad:
            self.assertEqual(self.submit("a", slots).status_code, 422, slots[:1])
        one_minute = self.submit("a", [slot(start=541, end=542)])
        self.assertEqual(one_minute.status_code, 200)  # 1-minute precision is allowed
        self.assertEqual(self.submit("a", [slot()], timeZone="UTC").status_code, 422)

    def test_access_rules(self) -> None:
        self.assertEqual(self.submit("stranger", [slot()]).status_code, 403)
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [self.user("p")["accountId"]]}, headers=self.h("host"))
        self.assertEqual(self.submit("p", [slot()]).status_code, 403)  # pending invitee has no membership yet
        no = self.client.get(f"/v2/rooms/{self.rid}/availability/me", headers=self.h("host")).json()
        self.assertEqual((no["status"], no["version"]), ("not_submitted", 0))
        self.assertEqual(self.client.put(f"/v2/rooms/{self.rid}/availability/me", json={"timeSlots": [slot()]}).status_code, 401)


class MinimumAttendeeTests(PotatoBase):
    def test_host_only_bounded_and_an_input_change(self) -> None:
        self.create_room()
        self.join("a", "민수")
        url = f"/v2/rooms/{self.rid}/minimum-attendees"
        self.assertEqual(self.client.put(url, json={"minimumAttendeeCount": 2}, headers=self.h("a")).status_code, 403)
        self.assertEqual(self.client.put(url, json={"minimumAttendeeCount": 1}, headers=self.h("host")).status_code, 422)
        too_many = self.client.put(url, json={"minimumAttendeeCount": 3}, headers=self.h("host"))
        self.assertEqual((too_many.status_code, too_many.json()["detail"]["code"]), (422, "MINIMUM_EXCEEDS_ELIGIBLE"))
        self.join("b", "철수")
        revision = self.room_row().agent_input_revision
        stale = self.client.put(url, json={"minimumAttendeeCount": 3, "expectedInputRevision": revision - 1}, headers=self.h("host"))
        self.assertEqual(stale.status_code, 409)
        ok = self.client.put(url, json={"minimumAttendeeCount": 3, "expectedInputRevision": revision}, headers=self.h("host"))
        self.assertEqual((ok.status_code, ok.json()["minimumAttendeeCount"]), (200, 3))
        self.assertEqual(self.room_row().agent_input_revision, revision + 1)
        same = self.client.put(url, json={"minimumAttendeeCount": 3}, headers=self.h("host"))
        self.assertTrue(same.json()["replayed"])
        self.assertEqual(self.room_row().agent_input_revision, revision + 1)


class EndToEndAgentTests(PotatoBase):
    def test_room_to_candidates(self) -> None:
        self.enable_exclusion()
        self.create_room()
        self.join("a", "민수")
        invitee = self.user("b")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.assertEqual(self.submit("host", [slot(start=540, end=720)]).status_code, 200)
        self.assertEqual(self.submit("a", [slot(start=600, end=780)]).status_code, 200)

        # Existing Agent policy: an unanswered invitee is neither absent nor ignored -
        # the Run waits for input instead of computing.
        first = self.start_run()
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(self.work().status, "WAITING_FOR_INPUT")

        # Only an explicit host exclusion (or the invitee's own answer) resolves it.
        excluded = self.client.post(f"/v2/rooms/{self.rid}/invitations/exclude",
                                    json={"accountId": invitee, "reason": "연락 안 됨"}, headers=self.h("host"))
        self.assertEqual(excluded.status_code, 200, excluded.text)
        self.assertEqual(self.run_row(first.json()["runId"]).status, "STALE")  # the input it waited on changed
        second = self.start_run("run-2")
        self.assertEqual(second.status_code, 202, second.text)
        run_id = second.json()["runId"]
        self.assertEqual(self.work().status, "ALL_AVAILABLE")
        candidates = self.client.get(f"/v2/rooms/{self.rid}/agent-runs/{run_id}/candidates", headers=self.h("host")).json()
        first_candidate = candidates["candidates"][0]
        self.assertEqual((first_candidate["candidateType"], len(first_candidate["members"]), first_candidate["verified"]),
                         ("ALL_AVAILABLE", 2, True))
        self.assertEqual(first_candidate["startsAt"][11:16], "10:00")

    def test_exclusion_is_disabled_by_default_because_no_rsvp_deadline_exists(self) -> None:
        self.create_room()
        invitee = self.user("b")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        r = self.client.post(f"/v2/rooms/{self.rid}/invitations/exclude",
                             json={"accountId": invitee, "reason": "x"}, headers=self.h("host"))
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "RSVP_DEADLINE_REQUIRED"))
        participants = self.client.get(f"/v2/rooms/{self.rid}/participants", headers=self.h("host")).json()["participants"]
        pending = next(p for p in participants if p["participantId"] == invitee)
        self.assertEqual((pending["participationStatus"], pending["eligibility"]), ("pending", "active"))

    def test_exclusion_rules(self) -> None:
        self.enable_exclusion()
        self.create_room()
        invitee = self.user("b")["accountId"]
        body = {"accountId": invitee, "reason": "x"}
        url = f"/v2/rooms/{self.rid}/invitations/exclude"
        self.assertEqual(self.client.post(url, json=body, headers=self.h("host")).status_code, 404)  # no invitation
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.assertEqual(self.client.post(url, json=body, headers=self.h("b")).status_code, 403)
        self.assertEqual(self.client.post(url, json={"accountId": invitee, "reason": ""}, headers=self.h("host")).status_code, 422)
        revision = self.room_row().agent_input_revision
        self.assertEqual(self.client.post(url, json=body, headers=self.h("host")).status_code, 200)
        replay = self.client.post(url, json=body, headers=self.h("host"))
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(self.room_row().agent_input_revision, revision + 1)  # exactly one input change
        self.assertEqual(self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "DECLINED"},
                                         headers=self.h("b")).status_code, 403)

    def test_answered_invitation_cannot_be_excluded(self) -> None:
        self.enable_exclusion()
        self.create_room()
        invitee = self.user("b")["accountId"]
        self.client.post(f"/v2/rooms/{self.rid}/invitations", json={"accountIds": [invitee]}, headers=self.h("host"))
        self.client.put(f"/v2/rooms/{self.rid}/invitations/me", json={"response": "DECLINED"}, headers=self.h("b"))
        r = self.client.post(f"/v2/rooms/{self.rid}/invitations/exclude", json={"accountId": invitee, "reason": "x"}, headers=self.h("host"))
        self.assertEqual((r.status_code, r.json()["detail"]["code"]), (409, "INVITATION_ALREADY_ANSWERED"))

    def test_input_change_invalidates_the_run_and_hash_moves_with_revision(self) -> None:
        self.create_room()
        self.join("a", "민수")
        self.submit("host", [slot()])
        self.submit("a", [slot()])
        run_id = self.start_run().json()["runId"]
        old = self.run_row(run_id)
        revision = self.room_row().agent_input_revision
        self.assertEqual(old.source_revision, revision)
        self.submit("a", [slot(start=600, end=700)])  # participant edits availability
        self.assertEqual(self.room_row().agent_input_revision, revision + 1)
        self.assertEqual(self.run_row(run_id).status, "STALE")
        again = self.start_run("run-2")
        self.assertEqual(again.status_code, 202, again.text)
        new = self.run_row(again.json()["runId"])
        self.assertEqual(new.source_revision, revision + 1)
        self.assertNotEqual(new.input_snapshot_hash, old.input_snapshot_hash)
        # a stale expected revision is refused by the existing Run API
        stale = self.client.post(f"/v2/rooms/{self.rid}/agent-runs", json={"expectedInputRevision": revision},
                                 headers=self.h("host", "run-3"))
        self.assertEqual((stale.status_code, stale.json()["detail"]["code"]), (409, "INPUT_REVISION_CONFLICT"))

    def test_missing_submission_is_waiting_for_input_not_absence(self) -> None:
        self.create_room()
        self.join("a", "민수")
        self.submit("host", [slot()])  # the other participant has not submitted
        self.assertEqual(self.start_run().status_code, 202)
        result = self.work()
        self.assertEqual(result.status, "WAITING_FOR_INPUT")
        self.assertEqual(result.candidates, ())

    def test_run_needs_two_eligible_participants_and_respects_the_minimum(self) -> None:
        self.create_room(key="solo")
        solo = self.start_run()
        self.assertEqual((solo.status_code, solo.json()["detail"]["code"]), (422, "INVALID_MEETING_SNAPSHOT"))
        self.create_room(key="min3", minimumAttendeeCount=3, nickname="방장2")
        self.join("a", "민수")  # 2 eligible < minimum 3
        self.assertEqual(self.start_run("r2").status_code, 422)


if __name__ == "__main__":
    unittest.main()
