"""Fixture tests for the standalone Agent Run worker loop (SQLite only)."""
from __future__ import annotations

import os
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import agent_routes
from agent_worker_main import WorkerConfig, run_worker
from db_v21.models.agent import AgentRun
from services.agent_worker import (
    AgentWorkerConfigurationError,
    claim_next_agent_run,
    execute_agent_run,
    request_agent_run_cancel,
)
from tests import test_meeting_snapshot


def _config(**overrides) -> WorkerConfig:
    values = dict(
        worker_id="w-test",
        poll_interval_seconds=0.01,
        lease_seconds=30,
        error_backoff_initial_seconds=0.01,
        error_backoff_max_seconds=0.02,
    )
    values.update(overrides)
    return WorkerConfig(**values)


class AgentWorkerLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.h = test_meeting_snapshot.MeetingSnapshotBuilderTests("setUp")
        self.h.setUp()
        self.addCleanup(self.h.db.close)
        self.engine = self.h.engine
        self.factory = lambda: Session(self.engine)
        self.stop = threading.Event()

    def _run_row(self, run_id: str) -> AgentRun:
        with Session(self.engine) as db:
            row = db.get(AgentRun, run_id)
            db.expunge(row)
            return row

    def _expire(self, run_id: str) -> None:
        with Session(self.engine) as db:
            db.get(AgentRun, run_id).lease_expires_at = datetime.now(
                timezone.utc
            ) - timedelta(seconds=1)
            db.commit()

    def _new_run(self) -> str:
        return self.h._create_solver_run(no_submission_start_minute=540).run_id

    def test_executes_queued_run_then_idles(self) -> None:
        run_id = self._new_run()
        self.assertEqual(run_worker(_config(), self.factory, self.stop, once=True), 1)
        row = self._run_row(run_id)
        self.assertEqual(row.status, "ALL_AVAILABLE")
        self.assertIsNone(row.worker_id)
        self.assertEqual(run_worker(_config(), self.factory, self.stop, once=True), 0)

    def test_duplicate_claim_is_rejected_while_lease_is_live(self) -> None:
        self._new_run()
        self.assertIsNotNone(
            claim_next_agent_run(self.factory, worker_id="a", lease_seconds=30)
        )
        other = _config(worker_id="b")
        self.assertEqual(run_worker(other, self.factory, self.stop, once=True), 0)

    def test_stale_owner_cannot_finish_after_lease_recovery(self) -> None:
        run_id = self._new_run()
        old = claim_next_agent_run(self.factory, worker_id="old", lease_seconds=30)
        self._expire(run_id)
        # New worker recovers the run and completes it.
        self.assertEqual(
            run_worker(_config(worker_id="new"), self.factory, self.stop, once=True), 1
        )
        row = self._run_row(run_id)
        self.assertEqual((row.status, row.attempt_number), ("ALL_AVAILABLE", 2))
        # The old owner's late result is discarded inside the worker loop.
        outcomes = []

        def late(claim, factory, **kw):
            try:
                return execute_agent_run(old, factory, **kw)
            except Exception as exc:  # recorded, then re-raised to the loop
                outcomes.append(type(exc).__name__)
                raise

        run_worker(
            _config(worker_id="old"), self.factory, self.stop, once=True,
            claim_fn=lambda *a, **k: old, execute_fn=late,
        )
        self.assertEqual(outcomes, ["WorkerLeaseLostError"])
        self.assertEqual(self._run_row(run_id).status, "ALL_AVAILABLE")

    def test_restart_after_crash_finishes_with_second_attempt(self) -> None:
        run_id = self._new_run()
        claim_next_agent_run(self.factory, worker_id="crashed", lease_seconds=30)
        self._expire(run_id)
        self.assertEqual(run_worker(_config(), self.factory, self.stop, once=True), 1)
        row = self._run_row(run_id)
        self.assertEqual((row.status, row.attempt_number), ("ALL_AVAILABLE", 2))

    def test_lease_expiry_at_max_attempts_fails_without_execution(self) -> None:
        run_id = self._new_run()
        for attempt in (1, 2, 3):
            claim_next_agent_run(
                self.factory, worker_id=f"dead-{attempt}", lease_seconds=30
            )
            self._expire(run_id)
        self.assertEqual(self._run_row(run_id).attempt_number, 3)
        self.assertEqual(run_worker(_config(), self.factory, self.stop, once=True), 0)
        row = self._run_row(run_id)
        self.assertEqual((row.status, row.error_code), ("FAILED", "WORKER_LEASE_EXHAUSTED"))

    def test_cancelled_queued_run_is_not_executed(self) -> None:
        run_id = self._new_run()
        self.assertTrue(request_agent_run_cancel(self.factory, run_id=run_id))
        self.assertEqual(run_worker(_config(), self.factory, self.stop, once=True), 0)
        self.assertEqual(self._run_row(run_id).status, "CANCELLED")

    def test_cancel_during_execution_discards_result(self) -> None:
        run_id = self._new_run()

        def execute(claim, factory, **kw):
            request_agent_run_cancel(factory, run_id=claim.run.run_id)
            return execute_agent_run(claim, factory, **kw)

        run_worker(_config(), self.factory, self.stop, once=True, execute_fn=execute)
        self.assertEqual(self._run_row(run_id).status, "CANCELLED")

    def test_solver_timeout_and_unknown_are_never_auto_retried(self) -> None:
        run_id = self._new_run()
        for code in ("SOLVER_TIMEOUT", "SOLVER_UNKNOWN"):
            with Session(self.engine) as db:
                row = db.get(AgentRun, run_id)
                row.status, row.error_code = "FAILED", code
                db.commit()
            self.assertEqual(run_worker(_config(), self.factory, self.stop, once=True), 0)
            row = self._run_row(run_id)
            self.assertEqual((row.status, row.error_code), ("FAILED", code))

    def test_graceful_shutdown_finishes_current_run_then_exits(self) -> None:
        run_id = self._new_run()

        def execute(claim, factory, **kw):
            self.stop.set()  # signal arrives mid-run
            return execute_agent_run(claim, factory, **kw)

        self.assertEqual(
            run_worker(_config(), self.factory, self.stop, execute_fn=execute), 1
        )
        self.assertEqual(self._run_row(run_id).status, "ALL_AVAILABLE")
        self.assertEqual(run_worker(_config(), self.factory, self.stop), 0)

    def test_db_outage_backs_off_and_recovers(self) -> None:
        run_id = self._new_run()
        attempts = []

        def flaky(factory, **kw):
            attempts.append(1)
            if len(attempts) <= 2:
                raise OperationalError("SELECT 1", {}, Exception("connection lost"))
            return claim_next_agent_run(factory, **kw)

        count = run_worker(
            _config(), self.factory, self.stop, max_runs=1, claim_fn=flaky
        )
        self.assertEqual((count, len(attempts)), (1, 3))
        self.assertEqual(self._run_row(run_id).status, "ALL_AVAILABLE")

    def test_execution_exception_does_not_kill_worker(self) -> None:
        self._new_run()

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        self.assertEqual(
            run_worker(_config(), self.factory, self.stop, once=True, execute_fn=boom), 1
        )

    def test_checkpointer_is_forwarded_only_when_configured(self) -> None:
        self._new_run()
        seen = []

        def spy(claim, factory, **kw):
            seen.append(kw.get("checkpointer"))
            return execute_agent_run(claim, factory, **{k: v for k, v in kw.items() if k != "checkpointer"})

        marker = object()
        run_worker(_config(), self.factory, self.stop, once=True,
                   execute_fn=spy, checkpointer=marker)
        self.assertEqual(seen, [marker])

    def test_max_runs_bounds_loop(self) -> None:
        run_id = self._new_run()
        self.assertEqual(run_worker(_config(), self.factory, self.stop, max_runs=0), 0)
        self.assertEqual(self._run_row(run_id).status, "QUEUED")


class WorkerConfigTests(unittest.TestCase):
    def test_env_parsing_and_validation(self) -> None:
        cfg = WorkerConfig.from_env(
            {"AGENT_WORKER_ID": "x", "AGENT_WORKER_LEASE_SECONDS": "90"}
        )
        self.assertEqual((cfg.worker_id, cfg.lease_seconds, cfg.max_attempts), ("x", 90, 3))
        with self.assertRaises(AgentWorkerConfigurationError):
            WorkerConfig.from_env({"AGENT_WORKER_LEASE_SECONDS": "abc"})
        with self.assertRaises(AgentWorkerConfigurationError):
            WorkerConfig.from_env({"AGENT_WORKER_LEASE_SECONDS": "1"})

    def test_checkpoint_backend_config(self) -> None:
        self.assertEqual(WorkerConfig.from_env({}).checkpoint_backend, "memory")
        with self.assertRaises(AgentWorkerConfigurationError):
            WorkerConfig.from_env({"AGENT_WORKER_CHECKPOINT_BACKEND": "postgres"})
        with self.assertRaises(AgentWorkerConfigurationError):
            WorkerConfig.from_env({"AGENT_WORKER_CHECKPOINT_BACKEND": "redis"})
        cfg = WorkerConfig.from_env({
            "AGENT_WORKER_CHECKPOINT_BACKEND": "postgres",
            "AGENT_WORKER_CHECKPOINT_DATABASE_URL": "postgresql://u:secret@h/db",
        })
        self.assertNotIn("secret", repr(cfg))

    def test_dispatch_setting(self) -> None:
        with patch.dict(os.environ):
            os.environ.pop("AGENT_WORKER_DISPATCH", None)
            self.assertEqual(agent_routes._worker_dispatch(), "NOT_CONFIGURED")
            os.environ["AGENT_WORKER_DISPATCH"] = "db_polling"
            self.assertEqual(agent_routes._worker_dispatch(), "DB_POLLING")
            os.environ["AGENT_WORKER_DISPATCH"] = "bogus"
            self.assertEqual(agent_routes._worker_dispatch(), "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
