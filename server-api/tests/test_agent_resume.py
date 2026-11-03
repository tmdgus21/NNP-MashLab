"""Durable checkpoint + guarded resume tests (SQLite saver; PostgreSQL gated)."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from db_v21.models.agent import AgentRun
from potato_agent.checkpoint import (
    CheckpointCorruptError,
    CheckpointMissingError,
    CheckpointUnavailableError,
    ResumeConflictError,
    open_postgres_checkpointer,
    run_thread_id,
)
from potato_agent.graph import checkpoint_serde
from services.agent_resume import (
    InvalidResumeRequestError,
    RunNotResumableError,
    StaleResumeError,
    resume_agent_run,
)
from services.agent_run import RoomHostRequiredError, RoomMembershipRequiredError
from services.agent_worker import (
    claim_next_agent_run,
    execute_agent_run,
    request_agent_run_cancel,
    retry_failed_agent_run,
)
from tests import test_meeting_snapshot

HOST = "account-host"


@contextmanager
def sqlite_saver(path: Path):
    from langgraph.checkpoint.sqlite import SqliteSaver

    connection = sqlite3.connect(str(path), check_same_thread=False)
    try:
        saver = SqliteSaver(connection, serde=checkpoint_serde())
        saver.setup()
        yield saver
    finally:
        connection.close()


class ResumeTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.h = test_meeting_snapshot.MeetingSnapshotBuilderTests("setUp")
        self.h.setUp()
        self.addCleanup(self.h.db.close)
        self.engine = self.h.engine
        self.factory = lambda: Session(self.engine)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ckpt = Path(tmp.name) / "checkpoints.sqlite"

    def _row(self, run_id: str) -> AgentRun:
        with Session(self.engine) as db:
            row = db.get(AgentRun, run_id)
            db.expunge(row)
            return row

    def _solve(self, *, checkpointer=None):
        run = self.h._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(self.factory, worker_id="w1", lease_seconds=30)
        extra = {"checkpointer": checkpointer} if checkpointer is not None else {}
        result = execute_agent_run(claim, self.factory, lease_seconds=30, **extra)
        self.assertEqual(result.status, "ALL_AVAILABLE")
        return run.run_id, result.candidates[0].candidate

    def _solve_durable(self):
        with sqlite_saver(self.ckpt) as saver:
            return self._solve(checkpointer=saver)

    def _resume(self, run_id, actor, kind, payload):
        with sqlite_saver(self.ckpt) as saver:  # a fresh saver == restarted process
            return resume_agent_run(
                self.factory, saver,
                run_id=run_id, actor_account_id=actor, kind=kind, payload=payload,
            )

    def _select(self, run_id, candidate, actor=HOST):
        return self._resume(
            run_id, actor, "candidate_selection",
            {"candidateId": candidate.candidate_id, "inputRevision": 5},
        )


class CheckpointRecoveryTests(ResumeTestBase):
    def test_worker_records_attempt_scoped_thread_and_checkpoint_ref(self) -> None:
        run_id, _ = self._solve_durable()
        row = self._row(run_id)
        self.assertEqual(row.checkpoint_thread_id, run_thread_id(run_id, 1))
        self.assertTrue(row.checkpoint_ref)

    def test_memory_checkpointer_run_has_no_durable_ref(self) -> None:
        run_id, candidate = self._solve()
        self.assertIsNone(self._row(run_id).checkpoint_ref)
        with self.assertRaises(CheckpointMissingError):
            self._select(run_id, candidate)

    def test_restart_resumes_selection_consents_and_host_approval(self) -> None:
        run_id, candidate = self._solve_durable()
        first_ref = self._row(run_id).checkpoint_ref

        outcome = self._select(run_id, candidate)  # new saver per step = restart
        self.assertEqual(outcome.next_pause_kind, "participant_consents")
        self.assertNotEqual(self._row(run_id).checkpoint_ref, first_ref)

        for attendee in candidate.attendee_ids:
            outcome = self._resume(
                run_id, attendee, "participant_consents",
                {
                    "participantId": attendee,
                    "candidateId": candidate.candidate_id,
                    "inputRevision": 5,
                    "consentRound": 1,
                    "decision": "AGREE",
                },
            )
        self.assertEqual(outcome.next_pause_kind, "host_approval")

        outcome = self._resume(
            run_id, HOST, "host_approval",
            {
                "actorParticipantId": HOST,
                "candidateId": candidate.candidate_id,
                "inputRevision": 5,
                "consentRound": 1,
                "decision": "APPROVE",
            },
        )
        self.assertEqual(outcome.approval_decision, "APPROVED")
        self.assertIsNone(outcome.next_pause_kind)
        # Policy untouched: resume never rewrites Run status or approval fields.
        row = self._row(run_id)
        self.assertEqual((row.status, row.approval_status), ("ALL_AVAILABLE", "NOT_REQUESTED"))

    def test_duplicate_resume_is_rejected(self) -> None:
        run_id, candidate = self._solve_durable()
        self._select(run_id, candidate)
        with self.assertRaises(ResumeConflictError):
            self._select(run_id, candidate)

    def test_cancelled_run_cannot_resume(self) -> None:
        run_id, candidate = self._solve_durable()
        with Session(self.engine) as db:
            db.get(AgentRun, run_id).cancel_requested_at = datetime.now(timezone.utc)
            db.commit()
        with self.assertRaises(RunNotResumableError):
            self._select(run_id, candidate)
        with Session(self.engine) as db:
            row = db.get(AgentRun, run_id)
            row.cancel_requested_at, row.status = None, "CANCELLED"
            db.commit()
        with self.assertRaises(RunNotResumableError):
            self._select(run_id, candidate)

    def test_changed_meeting_marks_run_stale_and_blocks_resume(self) -> None:
        run_id, candidate = self._solve_durable()
        with Session(self.engine) as db:
            from db_v21.models.room import Room

            db.get(Room, "room-1").agent_input_revision = 6
            db.commit()
        with self.assertRaises(StaleResumeError):
            self._select(run_id, candidate)
        self.assertEqual(self._row(run_id).status, "STALE")
        with self.assertRaises(RunNotResumableError):
            self._select(run_id, candidate)

    def test_run_reclaimed_after_lease_loss_blocks_old_checkpoint(self) -> None:
        run_id, candidate = self._solve_durable()
        with Session(self.engine) as db:  # simulate a requeued/re-leased run
            row = db.get(AgentRun, run_id)
            row.status, row.worker_id = "RUNNING", "w2"
            row.lease_token_hash, row.lease_expires_at = "x" * 64, datetime.now(
                timezone.utc
            ) + timedelta(seconds=30)
            db.commit()
        with self.assertRaises(RunNotResumableError):
            self._select(run_id, candidate)

    def test_retry_attempt_uses_a_fresh_thread(self) -> None:
        run_id, _ = self._solve_durable()
        first = self._row(run_id).checkpoint_thread_id
        with Session(self.engine) as db:  # force expired lease re-claim -> attempt 2
            row = db.get(AgentRun, run_id)
            row.status, row.worker_id = "RUNNING", "dead"
            row.lease_token_hash = "x" * 64
            row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        claim = claim_next_agent_run(self.factory, worker_id="w3", lease_seconds=30)
        self.assertEqual(claim.checkpoint_thread_id, run_thread_id(run_id, 2))
        self.assertNotEqual(claim.checkpoint_thread_id, first)

    def test_missing_checkpoint_in_store_is_typed(self) -> None:
        run_id, candidate = self._solve_durable()
        self.ckpt.unlink()  # store lost although the Run row still points at it
        with self.assertRaises(CheckpointMissingError):
            self._select(run_id, candidate)

    def test_corrupt_checkpoint_is_typed(self) -> None:
        run_id, candidate = self._solve_durable()
        connection = sqlite3.connect(str(self.ckpt))
        connection.execute("UPDATE checkpoints SET checkpoint = X'00FF00'")
        connection.commit()
        connection.close()
        with self.assertRaises(CheckpointCorruptError):
            self._select(run_id, candidate)

    def test_checkpoint_bound_to_wrong_thread_is_corrupt(self) -> None:
        run_id, candidate = self._solve_durable()
        with Session(self.engine) as db:
            db.get(AgentRun, run_id).checkpoint_thread_id = run_thread_id("other", 1)
            db.commit()
        with self.assertRaises(CheckpointCorruptError):
            self._select(run_id, candidate)

    def test_authorization_is_rechecked_against_the_database(self) -> None:
        run_id, candidate = self._solve_durable()
        with self.assertRaises(RoomMembershipRequiredError):
            self._select(run_id, candidate, actor="account-pending")
        self._select(run_id, candidate)
        with self.assertRaises(RoomHostRequiredError):
            self._resume(
                run_id, "account-member", "host_approval",
                {"actorParticipantId": "account-member"},
            )
        with self.assertRaises(InvalidResumeRequestError):
            self._resume(
                run_id, HOST, "host_approval", {"actorParticipantId": "account-member"}
            )
        with self.assertRaises(InvalidResumeRequestError):
            self._resume(run_id, HOST, "unknown_kind", {})

    def test_wrong_pending_step_is_a_conflict(self) -> None:
        run_id, _ = self._solve_durable()
        with self.assertRaises(ResumeConflictError):
            self._resume(
                run_id, HOST, "host_approval", {"actorParticipantId": HOST}
            )

    def test_checkpoint_outage_fails_run_as_retryable(self) -> None:
        import psycopg
        from langgraph.checkpoint.sqlite import SqliteSaver

        class FailingSaver(SqliteSaver):
            def put(self, *args, **kwargs):
                raise psycopg.OperationalError("connection lost")

        run = self.h._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(self.factory, worker_id="w1", lease_seconds=30)
        connection = sqlite3.connect(str(self.ckpt), check_same_thread=False)
        self.addCleanup(connection.close)
        saver = FailingSaver(connection, serde=checkpoint_serde())
        saver.setup()
        result = execute_agent_run(
            claim, self.factory, lease_seconds=30, checkpointer=saver
        )
        self.assertEqual((result.status, result.error_code), ("FAILED", "CHECKPOINT_UNAVAILABLE"))
        self.assertTrue(retry_failed_agent_run(self.factory, run_id=run.run_id))
        self.assertEqual(self._row(run.run_id).status, "QUEUED")

    def test_cancel_request_on_unfinished_queue_does_not_touch_checkpoints(self) -> None:
        run = self.h._create_solver_run(no_submission_start_minute=540)
        self.assertTrue(request_agent_run_cancel(self.factory, run_id=run.run_id))
        self.assertIsNone(self._row(run.run_id).checkpoint_ref)


class PostgresCheckpointTests(unittest.TestCase):
    def test_unreachable_postgres_is_typed_unavailable(self) -> None:
        with self.assertRaises(CheckpointUnavailableError):
            with open_postgres_checkpointer(
                "postgresql://u:p@127.0.0.1:1/none", connect_timeout_seconds=1.0
            ):
                pass

    @unittest.skipUnless(
        os.getenv("POTATO_TEST_POSTGRES_URL"),
        "SKIP: set POTATO_TEST_POSTGRES_URL to an isolated PostgreSQL database",
    )
    def test_postgres_saver_persists_across_reopen(self) -> None:
        from langgraph.checkpoint.base import empty_checkpoint

        url = os.environ["POTATO_TEST_POSTGRES_URL"]
        config = {
            "configurable": {"thread_id": f"pgtest:{os.getpid()}", "checkpoint_ns": ""}
        }
        with open_postgres_checkpointer(url, setup=True) as saver:
            saved = saver.put(config, empty_checkpoint(), {"source": "input", "step": 0}, {})
        with open_postgres_checkpointer(url) as saver:  # "restart"
            found = saver.get_tuple(saved)
        self.assertEqual(found.checkpoint["id"], saved["configurable"]["checkpoint_id"])


if __name__ == "__main__":
    unittest.main()
