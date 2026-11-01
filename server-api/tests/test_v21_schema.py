"""Schema v2.1 Alembic upgrade + inspector checks (disposable sqlite only)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "accounts",
    "account_sessions",
    "password_reset_tokens",
    "rooms",
    "room_members",
    "room_roles",
    "ai_drafts",
    "condition_submissions",
    "condition_available_slots",
    "condition_role_preferences",
    "proposals",
    "proposal_condition_inputs",
    "proposal_assignments",
    "proposal_consents",
    "service_controls",
    "room_controls",
    "admin_audit_logs",
    "announcements",
    "room_events",
    "admin_otps",
    "admin_rate_limits",
    "room_cycle_archives",
}


class V21SchemaTests(unittest.TestCase):
    def test_upgrade_creates_all_tables_and_key_uniques(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "v21.db"
            url = f"sqlite:///{db_path.as_posix()}"
            previous = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = url
            try:
                cfg = Config(str(ROOT / "alembic.v21.ini"))
                command.upgrade(cfg, "head")
            finally:
                if previous is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = previous

            engine = create_engine(url)
            try:
                insp = inspect(engine)
                tables = set(insp.get_table_names()) - {"alembic_version"}
                self.assertEqual(EXPECTED_TABLES, tables)
                self.assertEqual(22, len(tables))

                account_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("accounts")
                }
                account_indexes = {
                    tuple(ix["column_names"])
                    for ix in insp.get_indexes("accounts")
                    if ix.get("unique")
                }
                self.assertTrue(
                    ("login_email",) in account_uniques or ("login_email",) in account_indexes
                )

                room_indexes = {
                    tuple(ix["column_names"])
                    for ix in insp.get_indexes("rooms")
                    if ix.get("unique")
                }
                room_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("rooms")
                }
                self.assertTrue(("code",) in room_uniques or ("code",) in room_indexes)

                member_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("room_members")
                }
                self.assertIn(("room_id", "account_id"), member_uniques)
                self.assertIn(("room_id", "nickname"), member_uniques)

                role_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("room_roles")
                }
                self.assertIn(("room_id", "name"), role_uniques)

                submission_uniques = {
                    tuple(u["column_names"])
                    for u in insp.get_unique_constraints("condition_submissions")
                }
                self.assertIn(("room_member_id", "version"), submission_uniques)

                proposal_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("proposals")
                }
                self.assertIn(("room_id", "round"), proposal_uniques)

                member_fks = insp.get_foreign_keys("room_members")
                referred = {
                    (fk["referred_table"], tuple(fk["constrained_columns"])) for fk in member_fks
                }
                self.assertIn(("rooms", ("room_id",)), referred)
                self.assertIn(("accounts", ("account_id",)), referred)
            finally:
                engine.dispose()



if __name__ == "__main__":
    unittest.main()
