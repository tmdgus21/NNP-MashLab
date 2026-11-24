"""GET /join must work for Potato Meet rooms (title on rooms.title, not meeting_settings)."""
from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from database import Room, initialize, session
from public_routes import router as public_router
from schedule.constants import SEOUL
from schedule.router import router as schedule_router
from tests.auth_helpers import auth_headers, set_nickname
from user_auth import router as auth_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(schedule_router)
    app.include_router(public_router)
    return app


class PublicJoinTests(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        self.client = TestClient(_app())
        self.fixed = datetime(2026, 11, 20, 9, 0, tzinfo=SEOUL)

    def tearDown(self):
        self.client.close()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    @contextmanager
    def _frozen_clock(self):
        with (
            patch("schedule.service.utc_now", return_value=self.fixed),
            patch("schedule.service.seoul_now", return_value=self.fixed),
            patch("schedule.timeutil.seoul_today", return_value=self.fixed.date()),
        ):
            yield

    def test_join_page_for_schedule_created_room(self):
        """schedule.create_meeting stores title on the column only — must still return 200."""
        headers = auth_headers(self.client)
        set_nickname(self.client, headers, "방장")
        with self._frozen_clock():
            created = self.client.post(
                "/v1/meetings",
                headers=headers,
                json={
                    "title": "조인회귀",
                    "nickname": "방장",
                    "selectedDates": ["2026-11-20", "2026-11-26"],
                },
            )
        self.assertEqual(201, created.status_code, created.text)
        code = created.json()["code"]

        with session() as db:
            room = db.scalar(select(Room).where(Room.code == code))
            self.assertIsNotNone(room)
            self.assertEqual(room.title, "조인회귀")
            settings = room.meeting_settings if isinstance(room.meeting_settings, dict) else {}
            self.assertNotIn("title", settings)

        invite = self.client.get("/join", params={"code": code})
        self.assertEqual(200, invite.status_code, invite.text)
        self.assertIn("조인회귀", invite.text)
        self.assertIn("Potato Meet", invite.text)
        self.assertIn(code, invite.text)
        self.assertIn("Content-Security-Policy", invite.headers)
        self.assertIn("default-src 'none'", invite.headers["Content-Security-Policy"])
        self.assertEqual(invite.headers.get("X-Content-Type-Options"), "nosniff")

    def test_join_validation_unchanged(self):
        self.assertEqual(422, self.client.get("/join", params={"code": "invalid"}).status_code)
        self.assertEqual(
            404, self.client.get("/join", params={"code": "ABCD2345"}).status_code
        )


if __name__ == "__main__":
    unittest.main()
