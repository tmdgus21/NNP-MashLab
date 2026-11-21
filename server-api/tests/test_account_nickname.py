"""Account nickname generation, PATCH /me/nickname, same-nickname join."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import database as database_module

database_module._engine = None
from database import initialize
from nickname_generator import ADJECTIVES, FOODS, generate_nickname
from schedule.router import router as schedule_router
from tests.auth_helpers import auth_headers, register_verified
from user_auth import router as auth_router


def _near_dates(*offsets: int) -> list[str]:
    today = date.today()
    return [(today + timedelta(days=o)).isoformat() for o in offsets]


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(schedule_router)
    return app


class AccountNicknameTests(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        os.environ["ADMIN_ENABLED"] = "0"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        self.client = TestClient(_app())
        self.mail = patch("user_auth.send_otp_email", side_effect=lambda *a, **k: None)
        self.mail.start()

    def tearDown(self):
        self.mail.stop()
        self.client.close()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    def test_generator_shape(self):
        self.assertGreaterEqual(len(ADJECTIVES), 50)
        self.assertGreaterEqual(len(FOODS), 50)
        for _ in range(20):
            name = generate_nickname()
            self.assertLessEqual(len(name), 30)
            self.assertTrue(any(name.startswith(a) for a in ADJECTIVES))
            self.assertRegex(name, r"\d{3}$")

    def test_register_assigns_nickname_once(self):
        created = register_verified(self.client)
        self.assertIn("nickname", created)
        nick = created["nickname"]
        self.assertTrue(nick)
        self.assertLessEqual(len(nick), 30)
        headers = {"Authorization": "Bearer " + created["token"]}
        me = self.client.get("/v1/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["nickname"], nick)

    def test_patch_nickname_and_meeting_uses_account_nick(self):
        h1 = auth_headers(self.client)
        patched = self.client.patch(
            "/v1/auth/me/nickname",
            headers=h1,
            json={"nickname": "테스트닉네임"},
        )
        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertEqual(patched.json()["nickname"], "테스트닉네임")
        blank = self.client.patch(
            "/v1/auth/me/nickname",
            headers=h1,
            json={"nickname": "   "},
        )
        self.assertEqual(blank.status_code, 422)

        created = self.client.post(
            "/v1/meetings",
            headers=h1,
            json={
                "title": "닉테스트",
                "selectedDates": _near_dates(1, 3),
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertEqual(
            next(m["nickname"] for m in body["members"]),
            "테스트닉네임",
        )
        # Changing account nickname must not rewrite existing room_members row.
        self.client.patch(
            "/v1/auth/me/nickname",
            headers=h1,
            json={"nickname": "변경후닉"},
        )
        detail = self.client.get(f"/v1/meetings/{body['id']}", headers=h1).json()
        self.assertEqual(detail["members"][0]["nickname"], "테스트닉네임")

    def test_same_nickname_two_accounts_can_join(self):
        h1 = auth_headers(self.client)
        h2 = auth_headers(self.client)
        self.client.patch(
            "/v1/auth/me/nickname", headers=h1, json={"nickname": "같은이름"}
        )
        self.client.patch(
            "/v1/auth/me/nickname", headers=h2, json={"nickname": "같은이름"}
        )
        created = self.client.post(
            "/v1/meetings",
            headers=h1,
            json={
                "title": "중복닉",
                "nickname": "무시될닉",
                "selectedDates": _near_dates(2),
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(
            next(m["nickname"] for m in created.json()["members"]),
            "같은이름",
        )
        code = created.json()["code"]
        joined = self.client.post(
            "/v1/meetings/join",
            headers=h2,
            json={"code": code},
        )
        self.assertEqual(joined.status_code, 201, joined.text)
        members = joined.json()["members"]
        self.assertEqual(len(members), 2)
        self.assertEqual({m["nickname"] for m in members}, {"같은이름"})
        ids = {m["id"] for m in members}
        self.assertEqual(len(ids), 2)


if __name__ == "__main__":
    unittest.main()
