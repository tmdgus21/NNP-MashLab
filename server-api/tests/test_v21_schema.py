"""Schema v2.1 Alembic upgrade + inspector checks (disposable sqlite only)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


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
    "idempotency_records",
    "room_invitations",
    "agent_runs",
    "agent_candidates",
    "agent_candidate_members",
    "agent_change_proposals",
    "coordination_rounds",
}


class V21SchemaTests(unittest.TestCase):
    def test_orm_metadata_includes_agent_tables_and_constraints(self):
        from db_v21 import Base

        engine = create_engine("sqlite://")
        try:
            Base.metadata.create_all(engine)
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            self.assertEqual(EXPECTED_TABLES, tables)

            room_checks = {
                check["name"] for check in insp.get_check_constraints("rooms")
            }
            self.assertIn("ck_rooms_agent_input_revision", room_checks)

            invitation_checks = {
                check["name"]
                for check in insp.get_check_constraints("room_invitations")
            }
            self.assertIn(
                "ck_room_invitations_response_requires_sent", invitation_checks
            )

            candidate_uniques = {
                tuple(constraint["column_names"])
                for constraint in insp.get_unique_constraints("agent_candidates")
            }
            self.assertIn(("run_id", "rank"), candidate_uniques)
        finally:
            engine.dispose()

    def test_upgrade_creates_all_tables_and_key_uniques(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "v21.db"
            url = f"sqlite:///{db_path.as_posix()}"
            # Alembic env.py load_dotenv(.env) may inject ADMIN_ENABLED; snapshot and restore.
            previous_admin = os.environ.get("ADMIN_ENABLED")
            os.environ["DATABASE_URL"] = url
            try:
                cfg = Config(str(ROOT / "alembic.v21.ini"))
                command.upgrade(cfg, "20261101_0004")
                legacy_engine = create_engine(url)
                with legacy_engine.begin() as connection:
                    connection.exec_driver_sql(
                        """
                        INSERT INTO rooms (
                            id, code, title, starts_at, ends_at, lifecycle_status,
                            progress_status, meeting_settings, dirty, current_round,
                            revision, created_at, updated_at
                        ) VALUES (
                            'legacy-room', 'ABCDEFGH', 'Existing room',
                            '2026-11-02 00:00:00', '2026-11-03 00:00:00',
                            'COLLECTING_CONDITIONS', 'collecting', '{}', 1, 0,
                            7, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    )
                legacy_engine.dispose()
                command.upgrade(cfg, "head")
            finally:
                # Always return to in-memory sqlite for sibling unit tests in this process.
                os.environ["DATABASE_URL"] = "sqlite://"
                if previous_admin is None:
                    os.environ.pop("ADMIN_ENABLED", None)
                else:
                    os.environ["ADMIN_ENABLED"] = previous_admin
                import database as database_module

                database_module._engine = None

            engine = create_engine(url)
            try:
                insp = inspect(engine)
                tables = set(insp.get_table_names()) - {"alembic_version"}
                self.assertEqual(EXPECTED_TABLES, tables)
                self.assertEqual(28, len(tables))
                self.assertNotIn("room_cycle_archives", tables)

                room_cols = {c["name"] for c in insp.get_columns("rooms")}
                self.assertTrue(
                    {
                        "progress_status",
                        "meeting_settings",
                        "dirty",
                        "current_round",
                        "host_member_id",
                    }
                    <= room_cols
                )
                idem_cols = {c["name"] for c in insp.get_columns("idempotency_records")}
                self.assertIn("payload", idem_cols)

                ai_cols = {c["name"] for c in insp.get_columns("ai_drafts")}
                self.assertTrue(
                    {"raw_text", "model_output", "app_draft", "questions", "parse_status"}
                    <= ai_cols
                )

                cond_cols = {c["name"] for c in insp.get_columns("condition_submissions")}
                self.assertIn("confirmed", cond_cols)

                prop_cols = {c["name"] for c in insp.get_columns("proposals")}
                self.assertTrue({"input_snapshot", "plan", "round", "source_revision"} <= prop_cols)

                member_cols = {c["name"] for c in insp.get_columns("room_members")}
                self.assertTrue(
                    {"token_hash", "request_key_hash", "request_hash", "account_id"}
                    <= member_cols
                )

                account_indexes = {
                    tuple(ix["column_names"])
                    for ix in insp.get_indexes("accounts")
                    if ix.get("unique")
                }
                account_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("accounts")
                }
                self.assertTrue(
                    ("login_email",) in account_uniques or ("login_email",) in account_indexes
                )

                member_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("room_members")
                }
                self.assertIn(("room_id", "account_id"), member_uniques)
                self.assertIn(("room_id", "nickname"), member_uniques)

                proposal_uniques = {
                    tuple(u["column_names"]) for u in insp.get_unique_constraints("proposals")
                }
                self.assertIn(("room_id", "round"), proposal_uniques)

                idem_uniques = {
                    tuple(u["column_names"])
                    for u in insp.get_unique_constraints("idempotency_records")
                }
                self.assertIn(("scope", "key_hash"), idem_uniques)

                self.assertIn(
                    "agent_input_revision",
                    {c["name"] for c in insp.get_columns("rooms")},
                )
                with engine.connect() as connection:
                    preserved_room = connection.exec_driver_sql(
                        "SELECT revision, agent_input_revision, title "
                        "FROM rooms WHERE id='legacy-room'"
                    ).one()
                self.assertEqual((7, 1, "Existing room"), tuple(preserved_room))
                self.assertIn(
                    ("room_id", "account_id"),
                    {
                        tuple(u["column_names"])
                        for u in insp.get_unique_constraints("room_invitations")
                    },
                )
                self.assertIn(
                    ("run_id", "rank"),
                    {
                        tuple(u["column_names"])
                        for u in insp.get_unique_constraints("agent_candidates")
                    },
                )
                self.assertEqual(
                    ["candidate_id", "room_member_id", "consent_round"],
                    insp.get_pk_constraint("agent_candidate_members")[
                        "constrained_columns"
                    ],
                )
                with engine.connect() as connection:
                    consent_trigger = connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='trigger' "
                        "AND name='trg_agent_candidate_consent_immutable'"
                    ).scalar_one_or_none()
                self.assertIsNotNone(consent_trigger)
                with engine.connect() as connection:
                    snapshot_trigger = connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='trigger' "
                        "AND name='trg_agent_run_snapshot_immutable'"
                    ).scalar_one_or_none()
                self.assertIsNotNone(snapshot_trigger)

                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.exec_driver_sql(
                            """
                            INSERT INTO room_invitations (
                                id, room_id, account_id, invitation_status,
                                response_status, eligibility_status, created_at, updated_at
                            ) VALUES (
                                'invite', 'room', 'account', 'NOT_SENT',
                                'ACCEPTED', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                            )
                            """
                        )

                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.exec_driver_sql(
                            """
                            INSERT INTO agent_candidate_members (
                                candidate_id, room_member_id, consent_round,
                                participation_status, consent_status, consented_at
                            ) VALUES (
                                'candidate', 'member', 1,
                                'UNAVAILABLE', 'AGREE', CURRENT_TIMESTAMP
                            )
                            """
                        )

                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        """
                        INSERT INTO agent_candidate_members (
                            candidate_id, room_member_id, consent_round,
                            participation_status, consent_status, consented_at
                        ) VALUES (
                            'candidate', 'member', 1,
                            'ATTENDING', 'AGREE', CURRENT_TIMESTAMP
                        )
                        """
                    )
                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.exec_driver_sql(
                            """
                            UPDATE agent_candidate_members
                            SET consent_status = 'DISAGREE'
                            WHERE candidate_id = 'candidate'
                              AND room_member_id = 'member'
                              AND consent_round = 1
                            """
                        )

                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        """
                        INSERT INTO agent_runs (
                            id, agent_session_id, room_id, source_revision,
                            input_snapshot_hash, input_snapshot, consent_round,
                            status, approval_status, attempt_number, created_at, updated_at
                        ) VALUES (
                            'run', 'session', 'room', 1, :snapshot_hash, '{}', 1,
                            'ANALYZING', 'NOT_REQUESTED', 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """,
                        {"snapshot_hash": "a" * 64},
                    )
                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.exec_driver_sql(
                            "UPDATE agent_runs SET source_revision = 2 WHERE id = 'run'"
                        )
                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.exec_driver_sql(
                            "UPDATE agent_runs SET input_snapshot_hash = :hash "
                            "WHERE id = 'run'",
                            {"hash": "b" * 64},
                        )
                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.exec_driver_sql(
                            "UPDATE agent_runs SET input_snapshot = '{\"changed\":true}' "
                            "WHERE id = 'run'"
                        )

                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        """
                        INSERT INTO agent_runs (
                            id, agent_session_id, room_id, source_revision,
                            input_snapshot_hash, input_snapshot, consent_round,
                            status, approval_status, attempt_number, created_at, updated_at
                        ) VALUES (
                            'queued-run', 'queued-session', 'legacy-room', 1,
                            :snapshot_hash, '{}', 1, 'QUEUED', 'NOT_REQUESTED', 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """,
                        {"snapshot_hash": "c" * 64},
                    )
                    connection.exec_driver_sql(
                        """
                        INSERT INTO agent_runs (
                            id, agent_session_id, room_id, source_revision,
                            input_snapshot_hash, input_snapshot, consent_round,
                            status, approval_status, attempt_number, created_at, updated_at
                        ) VALUES (
                            'running-run', 'running-session', 'legacy-room', 1,
                            :snapshot_hash, '{}', 1, 'RUNNING', 'NOT_REQUESTED', 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """,
                        {"snapshot_hash": "e" * 64},
                    )
                    connection.exec_driver_sql(
                        """
                        INSERT INTO agent_runs (
                            id, agent_session_id, room_id, source_revision,
                            input_snapshot_hash, input_snapshot, consent_round,
                            status, approval_status, attempt_number, created_at, updated_at
                        ) VALUES (
                            'failed-run', 'failed-session', 'legacy-room', 1,
                            :snapshot_hash, '{}', 1, 'FAILED', 'NOT_REQUESTED', 1,
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """,
                        {"snapshot_hash": "f" * 64},
                    )
                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.exec_driver_sql(
                            """
                            INSERT INTO agent_runs (
                                id, agent_session_id, room_id, source_revision,
                                input_snapshot_hash, input_snapshot, consent_round,
                                status, approval_status, attempt_number, created_at, updated_at
                            ) VALUES (
                                'invalid-run', 'invalid-session', 'legacy-room', 1,
                                :snapshot_hash, '{}', 1, 'INVALID', 'NOT_REQUESTED', 1,
                                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                            )
                            """,
                            {"snapshot_hash": "d" * 64},
                        )

                os.environ["DATABASE_URL"] = url
                cfg = Config(str(ROOT / "alembic.v21.ini"))
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, "20261102_0006")
                with engine.connect() as connection:
                    self.assertEqual(
                        "20261102_0007",
                        connection.exec_driver_sql(
                            "SELECT version_num FROM alembic_version"
                        ).scalar_one(),
                    )
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        "DELETE FROM agent_runs WHERE id IN ('running-run', 'failed-run')"
                    )
                command.downgrade(cfg, "20261102_0006")
                with engine.connect() as connection:
                    self.assertEqual(
                        "20261102_0006",
                        connection.exec_driver_sql(
                            "SELECT version_num FROM alembic_version"
                        ).scalar_one(),
                    )
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, "20261102_0005")
                with engine.connect() as connection:
                    self.assertEqual(
                        "20261102_0006",
                        connection.exec_driver_sql(
                            "SELECT version_num FROM alembic_version"
                        ).scalar_one(),
                    )
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        "DELETE FROM agent_runs WHERE id = 'queued-run'"
                    )
                command.downgrade(cfg, "20261101_0004")
                os.environ["DATABASE_URL"] = "sqlite://"
                with engine.connect() as connection:
                    self.assertEqual(
                        "20261101_0004",
                        connection.exec_driver_sql(
                            "SELECT version_num FROM alembic_version"
                        ).scalar_one(),
                    )
                    self.assertNotIn(
                        "agent_runs",
                        inspect(connection).get_table_names(),
                    )
                    self.assertNotIn(
                        "agent_input_revision",
                        {
                            column["name"]
                            for column in inspect(connection).get_columns("rooms")
                        },
                    )
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
