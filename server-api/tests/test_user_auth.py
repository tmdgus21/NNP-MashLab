import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"
import secrets
import unittest
from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

import database as database_module

database_module._engine = None
from database import Account, initialize, session
from models import UserAuthChallenge, now
from fastapi import FastAPI
from user_auth import router as auth_router


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

        # Force resend window elapsed
        with session() as db, db.begin():
            row = db.scalar(
                select(UserAuthChallenge).where(UserAuthChallenge.challenge == challenge)
            )
            row.sent_at = now() - timedelta(seconds=61)
            row.expires_at = now() + timedelta(minutes=5)
            row.used_at = None
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


if __name__ == "__main__":
    unittest.main()
