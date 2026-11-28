"""Account-delete ownership transfer on isolated PostgreSQL (optional).

Skipped unless SCHEDULE_PG_URL is set. Never points at ops DB.
"""
from __future__ import annotations

import os
import secrets
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

PG_URL = os.environ.get("SCHEDULE_PG_URL", "")


@unittest.skipUnless(PG_URL, "SCHEDULE_PG_URL not set")
class AccountDeletePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = PG_URL
        os.environ["ADMIN_ENABLED"] = "0"
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine, text

        eng = create_engine(PG_URL)
        with eng.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE"))
            c.execute(text("CREATE SCHEMA public"))
        eng.dispose()
        root = Path(__file__).resolve().parents[1]
        command.upgrade(Config(str(root / "alembic.v21.ini")), "head")
        import database as database_module

        database_module._engine = None

    @classmethod
    def tearDownClass(cls):
        import database as database_module

        database_module._engine = None
        if cls._prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = cls._prev

    def test_owner_transfer_and_account_id_null(self):
        import database as database_module
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from database import Account, initialize, session
        from models import Room, RoomMember, uid
        from user_auth import ANONYMIZED_MEMBER_NICKNAME, router as auth_router

        database_module._engine = None
        initialize()
        app = FastAPI()
        app.include_router(auth_router)
        client = TestClient(app)
        codes: list[str] = []

        def _reg(email: str, password: str = "long-enough-password"):
            with patch(
                "user_auth.send_otp_email",
                side_effect=lambda e, code, **k: codes.append(code),
            ):
                started = client.post(
                    "/v1/auth/register", json={"email": email, "password": password}
                )
                self.assertEqual(201, started.status_code, started.text)
                verified = client.post(
                    "/v1/auth/register/verify",
                    json={"challenge": started.json()["challenge"], "code": codes[-1]},
                )
                self.assertEqual(200, verified.status_code, verified.text)
                return verified.json(), password

        host, host_pw = _reg(f"pg-host-{secrets.token_hex(3)}@example.test")
        member, _ = _reg(f"pg-mem-{secrets.token_hex(3)}@example.test")
        room_id = uid()
        host_mid = uid()
        mem_mid = uid()
        starts = datetime.now(timezone.utc)
        with session() as db:
            db.add(
                Room(
                    id=room_id,
                    code="PGDEL001",
                    title="PG탈퇴",
                    created_by_account_id=host["accountId"],
                    host_member_id=host_mid,
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
                    id=host_mid,
                    room_id=room_id,
                    account_id=host["accountId"],
                    nickname="PG방장",
                    room_role="OWNER",
                    membership_status="ACTIVE",
                )
            )
            db.add(
                RoomMember(
                    id=mem_mid,
                    room_id=room_id,
                    account_id=member["accountId"],
                    nickname="PG팀원",
                    room_role="MEMBER",
                    membership_status="ACTIVE",
                )
            )
            db.commit()

        deleted = client.request(
            "DELETE",
            "/v1/auth/me",
            headers={"Authorization": "Bearer " + host["token"]},
            json={"password": host_pw},
        )
        self.assertEqual(200, deleted.status_code, deleted.text)
        with session() as db:
            self.assertIsNone(db.get(Account, host["accountId"]))
            room = db.get(Room, room_id)
            self.assertEqual(mem_mid, room.host_member_id)
            self.assertIsNone(room.created_by_account_id)
            left = db.get(RoomMember, host_mid)
            self.assertIsNone(left.account_id)
            self.assertEqual(ANONYMIZED_MEMBER_NICKNAME, left.nickname)
            self.assertEqual("OWNER", db.get(RoomMember, mem_mid).room_role)
