import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"
import secrets
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select

import database as database_module
database_module._engine = None
from database import Account, initialize, session
from main import app
from models import Member


CONFIG = {
    "title": "계정 연동",
    "name": "방장",
    "dates": ["2026-10-17"],
    "roles": ["진행"],
    "duration": 60,
    "windowStart": 540,
    "windowEnd": 720,
}


class UserAuthTests(unittest.TestCase):
    def setUp(self):
        initialize()
        self.client = TestClient(app)
        self.email = f"user-{secrets.token_hex(4)}@example.test"
        self.password = "long-enough-password"

    def test_register_login_me_logout_and_guest_separation(self):
        created = self.client.post(
            "/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertEqual(body["email"], self.email)
        self.assertIn("token", body)
        headers = {"Authorization": "Bearer " + body["token"]}
        me = self.client.get("/v1/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["accountType"], "USER")

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
        self.assertEqual(
            self.client.post(
                "/v1/auth/logout",
                headers={"Authorization": "Bearer " + login.json()["token"]},
            ).status_code,
            200,
        )

        meeting = self.client.post("/v1/meetings", json=CONFIG)
        self.assertEqual(meeting.status_code, 201, meeting.text)
        with session() as db:
            member = db.get(Member, meeting.json()["actorId"])
            account = db.get(Account, member.account_id)
            self.assertEqual(account.account_type, "GUEST")

        linked = self.client.post(
            "/v1/meetings",
            json={**CONFIG, "name": "연동방장"},
            headers={"X-Account-Authorization": "Bearer " + body["token"]},
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        with session() as db:
            member = db.get(Member, linked.json()["actorId"])
            account = db.get(Account, member.account_id)
            self.assertEqual(account.account_type, "USER")
            self.assertEqual(account.login_email, self.email)
            guests = list(db.scalars(select(Account).where(Account.account_type == "GUEST")))
            users = list(db.scalars(select(Account).where(Account.login_email == self.email)))
            self.assertGreaterEqual(len(guests), 1)
            self.assertEqual(len(users), 1)


if __name__ == "__main__":
    unittest.main()
