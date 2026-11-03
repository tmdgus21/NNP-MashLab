"""Standalone DB-polling Agent Run worker.

Run: python agent_worker_main.py [--once] [--max-runs N]
One worker process executes one Run at a time. Existence of this process is
not tracked by the API; queued runs are only executed while a worker is alive.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import threading
from dataclasses import dataclass, field
from typing import Callable
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from services.agent_worker import (
    AgentRunClaim,
    AgentRunNotFoundError,
    AgentWorkerConfigurationError,
    WorkerLeaseLostError,
    claim_next_agent_run,
    execute_agent_run,
)

logger = logging.getLogger("agent_worker")


@dataclass(frozen=True)
class WorkerConfig:
    worker_id: str
    poll_interval_seconds: float = 2.0
    lease_seconds: int = 60
    heartbeat_interval_seconds: float | None = None
    solver_time_limit_seconds: float = 5.0
    max_attempts: int = 3
    error_backoff_initial_seconds: float = 1.0
    error_backoff_max_seconds: float = 30.0
    checkpoint_backend: str = "memory"
    checkpoint_database_url: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.worker_id or len(self.worker_id) > 128:
            raise AgentWorkerConfigurationError("worker_id must be 1..128 characters.")
        if self.poll_interval_seconds <= 0 or self.solver_time_limit_seconds <= 0:
            raise AgentWorkerConfigurationError("Intervals must be positive.")
        if self.lease_seconds < 3 or self.max_attempts < 1:
            raise AgentWorkerConfigurationError("Invalid lease or max attempts.")
        if not 0 < self.error_backoff_initial_seconds <= self.error_backoff_max_seconds:
            raise AgentWorkerConfigurationError("Invalid error backoff.")
        if self.checkpoint_backend not in ("memory", "postgres"):
            raise AgentWorkerConfigurationError("checkpoint_backend must be memory or postgres.")
        if self.checkpoint_backend == "postgres" and not self.checkpoint_database_url:
            raise AgentWorkerConfigurationError("postgres checkpoints need a database URL.")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "WorkerConfig":
        env = os.environ if env is None else env

        def get(name: str, cast, default):
            raw = env.get(f"AGENT_WORKER_{name}")
            try:
                return cast(raw) if raw not in (None, "") else default
            except ValueError as exc:
                raise AgentWorkerConfigurationError(
                    f"AGENT_WORKER_{name} is invalid."
                ) from exc

        return cls(
            worker_id=get(
                "ID", str, f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:8]}"
            ),
            poll_interval_seconds=get("POLL_INTERVAL_SECONDS", float, 2.0),
            lease_seconds=get("LEASE_SECONDS", int, 60),
            heartbeat_interval_seconds=get("HEARTBEAT_INTERVAL_SECONDS", float, None),
            solver_time_limit_seconds=get("SOLVER_TIME_LIMIT_SECONDS", float, 5.0),
            max_attempts=get("MAX_ATTEMPTS", int, 3),
            error_backoff_initial_seconds=get("ERROR_BACKOFF_INITIAL_SECONDS", float, 1.0),
            error_backoff_max_seconds=get("ERROR_BACKOFF_MAX_SECONDS", float, 30.0),
            checkpoint_backend=get("CHECKPOINT_BACKEND", str, "memory"),
            checkpoint_database_url=get("CHECKPOINT_DATABASE_URL", str, None),
        )


def run_worker(
    config: WorkerConfig,
    session_factory: Callable[[], Session],
    stop_event: threading.Event,
    *,
    max_runs: int | None = None,
    once: bool = False,
    checkpointer=None,
    claim_fn=claim_next_agent_run,
    execute_fn=execute_agent_run,
) -> int:
    """Poll-claim-execute loop. Returns the number of runs executed.

    No DB session is held while a Run is being computed; claim and execute use
    their own short sessions. SOLVER_TIMEOUT/UNKNOWN failures are never requeued
    here; only expired leases are recovered (inside the claim query).
    """
    executed = 0
    backoff = config.error_backoff_initial_seconds
    while not stop_event.is_set():
        if max_runs is not None and executed >= max_runs:
            break
        try:
            claim: AgentRunClaim | None = claim_fn(
                session_factory,
                worker_id=config.worker_id,
                lease_seconds=config.lease_seconds,
                max_attempts=config.max_attempts,
            )
        except Exception:
            logger.exception("claim failed; backing off %.1fs", backoff)
            if once:
                break
            stop_event.wait(backoff)
            backoff = min(backoff * 2, config.error_backoff_max_seconds)
            continue
        backoff = config.error_backoff_initial_seconds
        if claim is None:
            if once:
                break
            stop_event.wait(config.poll_interval_seconds)
            continue

        run_id = claim.run.run_id
        try:
            extra = {"checkpointer": checkpointer} if checkpointer is not None else {}
            result = execute_fn(
                claim,
                session_factory,
                lease_seconds=config.lease_seconds,
                heartbeat_interval_seconds=config.heartbeat_interval_seconds,
                time_limit_seconds=config.solver_time_limit_seconds,
                **extra,
            )
            executed += 1
            logger.info("run %s finished status=%s", run_id, result.status)
        except WorkerLeaseLostError:
            executed += 1
            logger.warning("run %s: lease lost; result discarded", run_id)
        except AgentRunNotFoundError:
            executed += 1
            logger.warning("run %s: no longer exists", run_id)
        except Exception:
            # Run is already terminalized FAILED when the DB was reachable;
            # otherwise its lease expires and the claim query recovers it.
            executed += 1
            logger.exception("run %s: execution error; backing off %.1fs", run_id, backoff)
            stop_event.wait(backoff)
            backoff = min(backoff * 2, config.error_backoff_max_seconds)
        if once:
            break
    return executed


def install_signal_handlers(stop_event: threading.Event) -> None:
    """First SIGINT/SIGTERM stops after the current Run; a second exits now.

    A forced exit leaves the lease to expire, after which the Run is recovered.
    """

    def handler(signum, _frame):
        if stop_event.is_set():
            raise SystemExit(1)
        logger.info("signal %s: finishing current run then exiting", signum)
        stop_event.set()

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Potato Meet Agent Run worker")
    parser.add_argument("--once", action="store_true", help="exit when the queue is empty")
    parser.add_argument("--max-runs", type=int, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=os.getenv("AGENT_WORKER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = WorkerConfig.from_env()
    import database

    factory = sessionmaker(database.engine(), expire_on_commit=False)
    stop_event = threading.Event()
    install_signal_handlers(stop_event)
    logger.info("worker %s starting", config.worker_id)
    if config.checkpoint_backend == "postgres":
        from potato_agent.checkpoint import open_postgres_checkpointer

        with open_postgres_checkpointer(config.checkpoint_database_url) as saver:
            run_worker(
                config, factory, stop_event,
                max_runs=args.max_runs, once=args.once, checkpointer=saver,
            )
    else:
        run_worker(config, factory, stop_event, max_runs=args.max_runs, once=args.once)
    logger.info("worker %s stopped", config.worker_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
