"""Single APK file serves /downloads/potato-meet.apk; /join link follows the same file."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import Room, initialize, session, uid
import public_routes as public_routes_mod
from public_routes import router as public_router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(public_router)
    return app


class PublicApkDownloadTests(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        self.tmp = tempfile.TemporaryDirectory()
        self.apk = Path(self.tmp.name) / "app-release.apk"
        self.apk.write_bytes(b"potato-meet-unified-apk")
        self._orig = public_routes_mod._APK_PATH
        public_routes_mod._APK_PATH = self.apk
        self.client = TestClient(_app())

    def tearDown(self):
        public_routes_mod._APK_PATH = self._orig
        self.client.close()
        self.tmp.cleanup()
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    def test_potato_meet_download_uses_apk_path(self):
        res = self.client.get("/downloads/potato-meet.apk")
        self.assertEqual(200, res.status_code)
        self.assertEqual(b"potato-meet-unified-apk", res.content)
        self.assertIn(
            "application/vnd.android.package-archive",
            res.headers.get("content-type", ""),
        )

    def test_conditional_ok_download_removed(self):
        self.assertEqual(404, self.client.get("/downloads/conditional-ok.apk").status_code)

    def test_missing_apk_404_and_join_hides_link(self):
        public_routes_mod._APK_PATH = Path(self.tmp.name) / "missing.apk"
        self.assertEqual(404, self.client.get("/downloads/potato-meet.apk").status_code)

        code = "JOINAPK2"
        with session() as db:
            db.add(
                Room(
                    id=uid(),
                    code=code,
                    title="APK링크",
                    starts_at=datetime.now(timezone.utc),
                    ends_at=datetime.now(timezone.utc) + timedelta(days=1),
                    lifecycle_status="COLLECTING_CONDITIONS",
                    progress_status="collecting",
                    meeting_settings={"selectedDates": ["2026-11-24"]},
                    revision=1,
                    dirty=False,
                    current_round=0,
                )
            )
            db.commit()

        invite = self.client.get("/join", params={"code": code})
        self.assertEqual(200, invite.status_code)
        self.assertNotIn("/downloads/potato-meet.apk", invite.text)
        self.assertIn("초대 코드로 참여", invite.text)

        public_routes_mod._APK_PATH = self.apk
        invite_ok = self.client.get("/join", params={"code": code})
        self.assertEqual(200, invite_ok.status_code)
        self.assertIn("/downloads/potato-meet.apk", invite_ok.text)
        self.assertIn("Android 앱 다운로드", invite_ok.text)


if __name__ == "__main__":
    unittest.main()
