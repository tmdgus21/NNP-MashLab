import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

import database as database_module

database_module._engine = None
from database import Account, initialize, session
from models import (
    AccountSession,
    Room,
    RoomEvent,
    RoomMember,
    UserAuthChallenge,
    now,
    uid,
)
from db_v21.models.schedule import (
    ScheduleCandidate,
    ScheduleCollection,
    ScheduleResponse,
    ScheduleResponseRange,
    ScheduleRun,
    ScheduleVote,
    ScheduleVoteBallot,
)
from fastapi import FastAPI
from user_auth import ANONYMIZED_MEMBER_NICKNAME, router as auth_router


def _app() -> FastAPI:
    # Avoid importing main/optimizer (ortools) for auth-focused coverage.
    app = FastAPI()
    app.include_router(auth_router)
    return app


class UserAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        os.environ["ADMIN_ENABLED"] = "0"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        self.client = TestClient(_app())
        self.email = f"user-{secrets.token_hex(4)}@example.test"
        self.password = "long-enough-password"
        self.codes = []
        self.mail = patch(
            "user_auth.send_otp_email",
            side_effect=lambda email, code, **kwargs: self.codes.append(code),
        )
        self.mail.start()

    def tearDown(self):
        self.mail.stop()
        self.client.close()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    def _register_verified(self):
        started = self.client.post(
            "/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(started.status_code, 201, started.text)
        body = started.json()
        self.assertIn("challenge", body)
        self.assertNotIn("token", body)
        self.assertTrue(self.codes)
        verified = self.client.post(
            "/v1/auth/register/verify",
            json={"challenge": body["challenge"], "code": self.codes[-1]},
        )
        self.assertEqual(verified.status_code, 200, verified.text)
        return verified.json()

    def test_register_login_otp_me_logout_and_guest_separation(self):
        created = self._register_verified()
        self.assertEqual(created["email"], self.email)
        self.assertIn("token", created)
        headers = {"Authorization": "Bearer " + created["token"]}
        me = self.client.get("/v1/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["accountType"], "USER")
        self.assertTrue(me.json().get("nickname"))
        self.assertEqual(created.get("nickname"), me.json()["nickname"])

        self.assertEqual(
            self.client.post(
                "/v1/auth/register",
                json={"email": self.email, "password": self.password},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                "/v1/auth/register",
                json={"email": "x@local.invalid", "password": self.password},
            ).status_code,
            422,
        )

        login = self.client.post(
            "/v1/auth/login",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertIn("challenge", login.json())
        self.assertNotIn("token", login.json())
        verified_login = self.client.post(
            "/v1/auth/login/verify",
            json={"challenge": login.json()["challenge"], "code": self.codes[-1]},
        )
        self.assertEqual(verified_login.status_code, 200, verified_login.text)
        self.assertEqual(
            self.client.post(
                "/v1/auth/logout",
                headers={"Authorization": "Bearer " + verified_login.json()["token"]},
            ).status_code,
            200,
        )

        # Existing session from register still works (OTP only on new login).
        self.assertEqual(self.client.get("/v1/auth/me", headers=headers).status_code, 200)
        with session() as db:
            users = list(
                db.scalars(
                    select(Account).where(
                        Account.login_email == self.email, Account.account_type == "USER"
                    )
                )
            )
            self.assertEqual(1, len(users))
            self.assertTrue(users[0].approved)
            self.assertEqual("ACTIVE", users[0].account_status)

    def test_register_rejects_before_otp_and_wrong_code(self):
        started = self.client.post(
            "/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(started.status_code, 201, started.text)
        with session() as db:
            users = list(
                db.scalars(
                    select(Account).where(
                        Account.login_email == self.email, Account.account_type == "USER"
                    )
                )
            )
            self.assertEqual(users, [])
        bad = self.client.post(
            "/v1/auth/register/verify",
            json={"challenge": started.json()["challenge"], "code": "000000"},
        )
        self.assertEqual(bad.status_code, 401, bad.text)

    def test_otp_expiry_and_resend(self):
        started = self.client.post(
            "/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        challenge = started.json()["challenge"]
        with session() as db, db.begin():
            row = db.scalar(
                select(UserAuthChallenge).where(UserAuthChallenge.challenge == challenge)
            )
            row.sent_at = now() - timedelta(minutes=10)
            row.expires_at = now() - timedelta(seconds=1)
        expired = self.client.post(
            "/v1/auth/register/verify",
            json={"challenge": challenge, "code": self.codes[-1]},
        )
        self.assertEqual(expired.status_code, 401, expired.text)

        # Expired challenges may still be resent (60s window already elapsed via sent_at).
        resent = self.client.post(
            "/v1/auth/register/resend",
            json={"challenge": challenge},
        )
        self.assertEqual(resent.status_code, 200, resent.text)
        self.assertNotEqual(resent.json()["challenge"], challenge)
        ok = self.client.post(
            "/v1/auth/register/verify",
            json={"challenge": resent.json()["challenge"], "code": self.codes[-1]},
        )
        self.assertEqual(ok.status_code, 200, ok.text)

    def test_otp_max_attempts(self):
        started = self.client.post(
            "/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        challenge = started.json()["challenge"]
        for _ in range(5):
            self.assertEqual(
                self.client.post(
                    "/v1/auth/register/verify",
                    json={"challenge": challenge, "code": "111111"},
                ).status_code,
                401,
            )
        locked = self.client.post(
            "/v1/auth/register/verify",
            json={"challenge": challenge, "code": self.codes[-1]},
        )
        self.assertEqual(locked.status_code, 429, locked.text)

    def test_code_not_in_api_responses(self):
        started = self.client.post(
            "/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        text = started.text
        self.assertNotIn(self.codes[-1], text)
        with session() as db:
            row = db.scalar(select(UserAuthChallenge).limit(1))
            self.assertNotEqual(row.code_digest, self.codes[-1])
            self.assertEqual(64, len(row.code_digest))

    def test_delete_account_without_meetings(self):
        created = self._register_verified()
        token = created["token"]
        account_id = created["accountId"]
        headers = {"Authorization": "Bearer " + token}

        bad_auth = self.client.request(
            "DELETE",
            "/v1/auth/me",
            json={"password": self.password},
        )
        self.assertEqual(401, bad_auth.status_code)

        wrong = self.client.request(
            "DELETE",
            "/v1/auth/me",
            headers=headers,
            json={"password": "wrong-password-xx"},
        )
        self.assertEqual(403, wrong.status_code)
        self.assertEqual(200, self.client.get("/v1/auth/me", headers=headers).status_code)

        deleted = self.client.request(
            "DELETE",
            "/v1/auth/me",
            headers=headers,
            json={"password": self.password},
        )
        self.assertEqual(200, deleted.status_code, deleted.text)
        self.assertTrue(deleted.json().get("deleted"))

        self.assertEqual(401, self.client.get("/v1/auth/me", headers=headers).status_code)
        with session() as db:
            self.assertIsNone(db.get(Account, account_id))
            self.assertEqual(
                [],
                list(
                    db.scalars(
                        select(AccountSession).where(AccountSession.account_id == account_id)
                    )
                ),
            )
            self.assertEqual(
                [],
                list(
                    db.scalars(select(UserAuthChallenge).where(UserAuthChallenge.email == self.email))
                ),
            )

        # Same email may register again after hard delete.
        again = self._register_verified()
        self.assertNotEqual(account_id, again["accountId"])

    def test_delete_account_anonymizes_membership_keeps_others(self):
        host = self._register_verified()
        other_email = f"other-{secrets.token_hex(4)}@example.test"
        other_password = "long-enough-password"
        started = self.client.post(
            "/v1/auth/register",
            json={"email": other_email, "password": other_password},
        )
        self.assertEqual(201, started.status_code, started.text)
        other = self.client.post(
            "/v1/auth/register/verify",
            json={"challenge": started.json()["challenge"], "code": self.codes[-1]},
        ).json()

        room_id = uid()
        host_member_id = uid()
        other_member_id = uid()
        starts = datetime.now(timezone.utc)
        with session() as db:
            db.add(
                Room(
                    id=room_id,
                    code="DELTEST1",
                    title="탈퇴모임",
                    created_by_account_id=host["accountId"],
                    host_member_id=host_member_id,
                    starts_at=starts,
                    ends_at=starts + timedelta(days=2),
                    lifecycle_status="COLLECTING_CONDITIONS",
                    progress_status="collecting",
                    meeting_settings={},
                    revision=1,
                    dirty=False,
                    current_round=0,
                )
            )
            db.add(
                RoomMember(
                    id=host_member_id,
                    room_id=room_id,
                    account_id=host["accountId"],
                    nickname="방장닉",
                    room_role="OWNER",
                    membership_status="ACTIVE",
                )
            )
            db.add(
                RoomMember(
                    id=other_member_id,
                    room_id=room_id,
                    account_id=other["accountId"],
                    nickname="팀원닉",
                    room_role="MEMBER",
                    membership_status="ACTIVE",
                )
            )
            db.commit()

        deleted = self.client.request(
            "DELETE",
            "/v1/auth/me",
            headers={"Authorization": "Bearer " + host["token"]},
            json={"password": self.password},
        )
        self.assertEqual(200, deleted.status_code, deleted.text)

        with session() as db:
            self.assertIsNone(db.get(Account, host["accountId"]))
            self.assertIsNotNone(db.get(Account, other["accountId"]))
            room = db.get(Room, room_id)
            self.assertIsNotNone(room)
            self.assertEqual("collecting", room.progress_status)
            self.assertIsNone(room.created_by_account_id)
            self.assertEqual(other_member_id, room.host_member_id)
            host_member = db.get(RoomMember, host_member_id)
            other_member = db.get(RoomMember, other_member_id)
            self.assertEqual(ANONYMIZED_MEMBER_NICKNAME, host_member.nickname)
            self.assertEqual("LEFT", host_member.membership_status)
            self.assertEqual("MEMBER", host_member.room_role)
            self.assertIsNone(host_member.account_id)
            self.assertIsNone(host_member.token_hash)
            self.assertIsNone(host_member.request_key_hash)
            self.assertIsNone(host_member.request_hash)
            self.assertEqual("팀원닉", other_member.nickname)
            self.assertEqual("ACTIVE", other_member.membership_status)
            self.assertEqual("OWNER", other_member.room_role)
            self.assertEqual(other["accountId"], other_member.account_id)

        other_me = self.client.get(
            "/v1/auth/me",
            headers={"Authorization": "Bearer " + other["token"]},
        )
        self.assertEqual(200, other_me.status_code)

    def test_delete_account_wrong_password_rolls_back_membership(self):
        created = self._register_verified()
        room_id = uid()
        member_id = uid()
        starts = datetime.now(timezone.utc)
        with session() as db:
            db.add(
                Room(
                    id=room_id,
                    code="DELFAIL1",
                    title="롤백모임",
                    created_by_account_id=created["accountId"],
                    host_member_id=member_id,
                    starts_at=starts,
                    ends_at=starts + timedelta(days=1),
                    lifecycle_status="COLLECTING_CONDITIONS",
                    progress_status="collecting",
                    meeting_settings={},
                    revision=1,
                    dirty=False,
                    current_round=0,
                )
            )
            db.add(
                RoomMember(
                    id=member_id,
                    room_id=room_id,
                    account_id=created["accountId"],
                    nickname="유지닉",
                    room_role="OWNER",
                    membership_status="ACTIVE",
                    token_hash="a" * 64,
                    request_key_hash="b" * 64,
                    request_hash="c" * 64,
                )
            )
            db.commit()

        bad = self.client.request(
            "DELETE",
            "/v1/auth/me",
            headers={"Authorization": "Bearer " + created["token"]},
            json={"password": "not-the-real-password"},
        )
        self.assertEqual(403, bad.status_code)
        with session() as db:
            self.assertIsNotNone(db.get(Account, created["accountId"]))
            member = db.get(RoomMember, member_id)
            self.assertEqual("유지닉", member.nickname)
            self.assertEqual("ACTIVE", member.membership_status)
            self.assertEqual(created["accountId"], member.account_id)
            self.assertEqual("a" * 64, member.token_hash)

    def test_delete_last_owner_soft_deletes_room(self):
        created = self._register_verified()
        room_id = uid()
        member_id = uid()
        starts = datetime.now(timezone.utc)
        with session() as db:
            db.add(
                Room(
                    id=room_id,
                    code="DELEMPT1",
                    title="빈모임",
                    created_by_account_id=created["accountId"],
                    host_member_id=member_id,
                    starts_at=starts,
                    ends_at=starts + timedelta(days=1),
                    lifecycle_status="COLLECTING_CONDITIONS",
                    progress_status="collecting",
                    meeting_settings={},
                    revision=1,
                    dirty=False,
                    current_round=0,
                )
            )
            db.add(
                RoomMember(
                    id=member_id,
                    room_id=room_id,
                    account_id=created["accountId"],
                    nickname="유일방장",
                    room_role="OWNER",
                    membership_status="ACTIVE",
                )
            )
            db.commit()

        deleted = self.client.request(
            "DELETE",
            "/v1/auth/me",
            headers={"Authorization": "Bearer " + created["token"]},
            json={"password": self.password},
        )
        self.assertEqual(200, deleted.status_code, deleted.text)
        with session() as db:
            room = db.get(Room, room_id)
            self.assertEqual("deleted", room.progress_status)
            self.assertIsNotNone(room.deleted_at)
            member = db.get(RoomMember, member_id)
            self.assertEqual("LEFT", member.membership_status)
            self.assertIsNone(member.account_id)

    def test_delete_purges_schedule_pii_and_scrubs_summary(self):
        leaver = self._register_verified()
        keeper_email = f"keep-{secrets.token_hex(4)}@example.test"
        started = self.client.post(
            "/v1/auth/register",
            json={"email": keeper_email, "password": "long-enough-password"},
        )
        keeper = self.client.post(
            "/v1/auth/register/verify",
            json={"challenge": started.json()["challenge"], "code": self.codes[-1]},
        ).json()

        room_id = uid()
        leave_member = uid()
        keep_member = uid()
        collection_id = uid()
        run_id = uid()
        candidate_id = uid()
        starts = datetime.now(timezone.utc)
        with session() as db:
            db.add(
                Room(
                    id=room_id,
                    code="DELPII01",
                    title="개인정보모임",
                    created_by_account_id=keeper["accountId"],
                    host_member_id=keep_member,
                    starts_at=starts,
                    ends_at=starts + timedelta(days=2),
                    lifecycle_status="COLLECTING_CONDITIONS",
                    progress_status="reviewing",
                    meeting_settings={},
                    revision=2,
                    dirty=False,
                    current_round=0,
                )
            )
            db.add(
                RoomMember(
                    id=leave_member,
                    room_id=room_id,
                    account_id=leaver["accountId"],
                    nickname="떠날사람",
                    room_role="MEMBER",
                    membership_status="ACTIVE",
                    token_hash="d" * 64,
                    request_key_hash="e" * 64,
                    request_hash="f" * 64,
                )
            )
            db.add(
                RoomMember(
                    id=keep_member,
                    room_id=room_id,
                    account_id=keeper["accountId"],
                    nickname="남을사람",
                    room_role="OWNER",
                    membership_status="ACTIVE",
                )
            )
            db.add(
                ScheduleCollection(
                    id=collection_id,
                    room_id=room_id,
                    cycle=0,
                    kind="NORMAL",
                    scope_starts_at=starts,
                    scope_ends_at=starts + timedelta(days=1),
                    closes_at=starts + timedelta(hours=12),
                    status="CLOSED",
                    closed_at=starts + timedelta(hours=1),
                    closed_reason="ALL_DONE",
                )
            )
            db.add(
                ScheduleResponse(collection_id=collection_id, room_member_id=leave_member)
            )
            db.add(
                ScheduleResponse(collection_id=collection_id, room_member_id=keep_member)
            )
            db.add(
                ScheduleResponseRange(
                    id=uid(),
                    collection_id=collection_id,
                    room_member_id=leave_member,
                    starts_at=starts + timedelta(hours=2),
                    ends_at=starts + timedelta(hours=3),
                )
            )
            db.add(
                ScheduleResponseRange(
                    id=uid(),
                    collection_id=collection_id,
                    room_member_id=keep_member,
                    starts_at=starts + timedelta(hours=2),
                    ends_at=starts + timedelta(hours=4),
                )
            )
            db.add(
                ScheduleRun(
                    id=run_id,
                    room_id=room_id,
                    collection_id=collection_id,
                    max_count=2,
                    participant_count=2,
                    voter_count=2,
                    ai_summary=f"떠날사람과 {self.email} 님이 가능합니다.",
                )
            )
            db.add(
                ScheduleCandidate(
                    id=candidate_id,
                    run_id=run_id,
                    room_id=room_id,
                    starts_at=starts + timedelta(hours=2),
                    ends_at=starts + timedelta(hours=3),
                    available_count=2,
                    sort_order=1,
                )
            )
            db.add(
                ScheduleVote(
                    candidate_id=candidate_id,
                    room_member_id=leave_member,
                    room_id=room_id,
                )
            )
            db.add(
                ScheduleVote(
                    candidate_id=candidate_id,
                    room_member_id=keep_member,
                    room_id=room_id,
                )
            )
            db.add(ScheduleVoteBallot(run_id=run_id, room_member_id=leave_member))
            db.add(ScheduleVoteBallot(run_id=run_id, room_member_id=keep_member))
            db.add(
                RoomEvent(
                    id=uid(),
                    room_id=room_id,
                    actor_member_id=leave_member,
                    event_type="MEMBER_JOINED",
                    message=f"떠날사람({self.email}) 참여",
                )
            )
            db.commit()

        deleted = self.client.request(
            "DELETE",
            "/v1/auth/me",
            headers={"Authorization": "Bearer " + leaver["token"]},
            json={"password": self.password},
        )
        self.assertEqual(200, deleted.status_code, deleted.text)

        with session() as db:
            self.assertIsNone(db.get(Account, leaver["accountId"]))
            self.assertIsNotNone(db.get(Account, keeper["accountId"]))
            room = db.get(Room, room_id)
            self.assertEqual("reviewing", room.progress_status)
            self.assertEqual(keep_member, room.host_member_id)
            self.assertEqual(
                0,
                len(
                    list(
                        db.scalars(
                            select(ScheduleResponse).where(
                                ScheduleResponse.room_member_id == leave_member
                            )
                        )
                    )
                ),
            )
            self.assertEqual(
                1,
                len(
                    list(
                        db.scalars(
                            select(ScheduleResponse).where(
                                ScheduleResponse.room_member_id == keep_member
                            )
                        )
                    )
                ),
            )
            self.assertEqual(
                0,
                len(
                    list(
                        db.scalars(
                            select(ScheduleResponseRange).where(
                                ScheduleResponseRange.room_member_id == leave_member
                            )
                        )
                    )
                ),
            )
            self.assertEqual(
                1,
                len(
                    list(
                        db.scalars(
                            select(ScheduleVote).where(
                                ScheduleVote.room_member_id == keep_member
                            )
                        )
                    )
                ),
            )
            self.assertEqual(
                0,
                len(
                    list(
                        db.scalars(
                            select(ScheduleVote).where(
                                ScheduleVote.room_member_id == leave_member
                            )
                        )
                    )
                ),
            )
            self.assertIsNone(db.get(ScheduleVoteBallot, (run_id, leave_member)))
            run = db.get(ScheduleRun, run_id)
            self.assertNotIn("떠날사람", run.ai_summary or "")
            self.assertNotIn(self.email, run.ai_summary or "")
            self.assertIn(ANONYMIZED_MEMBER_NICKNAME, run.ai_summary or "")
            event = db.scalar(select(RoomEvent).where(RoomEvent.room_id == room_id))
            self.assertNotIn(self.email, event.message)
            self.assertNotIn("떠날사람", event.message)
            left = db.get(RoomMember, leave_member)
            self.assertIsNone(left.token_hash)
            self.assertIsNone(left.request_hash)


if __name__ == "__main__":
    unittest.main()
