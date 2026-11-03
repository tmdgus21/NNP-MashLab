"""Durable checkpoint helpers: typed errors, thread contract, guarded resume.

Responsibility split: the Agent Run row in the application DB is authoritative
for status, ownership, revision and permissions. A checkpoint only stores
graph-internal state (snapshot, candidates, pending interrupt). A checkpoint is
reachable solely through the server-derived ``run_thread_id`` -- clients never
supply thread or checkpoint identifiers.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from langgraph.types import Command


class CheckpointError(Exception):
    code = "CHECKPOINT_ERROR"
    retryable = False


class CheckpointMissingError(CheckpointError):
    code = "CHECKPOINT_MISSING"


class CheckpointCorruptError(CheckpointError):
    code = "CHECKPOINT_CORRUPT"


class CheckpointUnavailableError(CheckpointError):
    code = "CHECKPOINT_UNAVAILABLE"
    retryable = True


class ResumeNotPendingError(CheckpointError):
    """The run has no pending interrupt: the resume was already applied or the graph ended."""

    code = "RESUME_NOT_PENDING"


class ResumeConflictError(CheckpointError):
    """The pending interrupt differs from what the caller expected."""

    code = "RESUME_CONFLICT"


def run_thread_id(run_id: str, attempt_number: int) -> str:
    """Stable thread for one attempt of one run; a retry never reuses old state."""
    if not run_id or attempt_number < 1:
        raise ValueError("run_id and a positive attempt_number are required.")
    return f"agent-run:{run_id}:a{attempt_number}"


def thread_config(thread_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
    configurable = {"thread_id": thread_id}
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


def _is_connection_error(exc: BaseException) -> bool:
    try:
        import psycopg
        import psycopg_pool
    except ImportError:  # pragma: no cover - PostgreSQL extras not installed
        return False
    return isinstance(
        exc, (psycopg.OperationalError, psycopg_pool.PoolTimeout, psycopg_pool.PoolClosed)
    )


@contextmanager
def map_checkpoint_errors(*, unreadable_is_corrupt: bool = True) -> Iterator[None]:
    """Translate storage failures into typed checkpoint errors.

    With ``unreadable_is_corrupt=False`` only connection failures are mapped, so
    domain errors raised by graph nodes (e.g. stale revision) pass through.
    """
    try:
        yield
    except CheckpointError:
        raise
    except Exception as exc:
        if _is_connection_error(exc):
            raise CheckpointUnavailableError("Checkpoint store is unavailable.") from exc
        if not unreadable_is_corrupt:
            raise
        raise CheckpointCorruptError(
            f"Checkpoint could not be read: {type(exc).__name__}"
        ) from exc


@contextmanager
def open_postgres_checkpointer(
    conninfo: str, *, setup: bool = False, connect_timeout_seconds: float = 10.0
) -> Iterator[Any]:
    """PostgresSaver on a reconnecting pool (survives DB restarts).

    ``setup=True`` runs LangGraph's own idempotent table migrations; do it in a
    deliberate deploy step rather than at every worker start.
    """
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    from potato_agent.graph import checkpoint_serde

    pool = ConnectionPool(
        conninfo,
        min_size=1,
        max_size=4,
        timeout=connect_timeout_seconds,
        open=False,
        check=ConnectionPool.check_connection,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    try:
        with map_checkpoint_errors():
            pool.open(wait=True, timeout=connect_timeout_seconds)
    except BaseException:
        pool.close(timeout=0)
        raise
    try:
        saver = PostgresSaver(pool, serde=checkpoint_serde())
        if setup:
            with map_checkpoint_errors():
                saver.setup()
        yield saver
    finally:
        pool.close()


def latest_checkpoint_id(graph: Any, thread_id: str) -> str | None:
    with map_checkpoint_errors():
        state = graph.get_state(thread_config(thread_id))
    return state.config["configurable"].get("checkpoint_id") if state.config else None


def pending_interrupt(
    graph: Any, thread_id: str, checkpoint_id: str | None = None
) -> tuple[str, dict[str, Any], str]:
    """Return (kind, payload, checkpoint_id) of the single pending interrupt.

    Raises CheckpointMissingError when no checkpoint exists for the thread,
    ResumeNotPendingError when the graph is not paused, and
    CheckpointCorruptError for unreadable or malformed state.
    """
    with map_checkpoint_errors():
        state = graph.get_state(thread_config(thread_id, checkpoint_id))
    if not state.config or not state.config.get("configurable", {}).get("checkpoint_id"):
        raise CheckpointMissingError("No checkpoint exists for this run.")
    checkpoint_id = state.config["configurable"]["checkpoint_id"]
    if not state.values:
        raise CheckpointCorruptError("Checkpoint holds no graph state.")
    interrupts = [i for task in state.tasks for i in task.interrupts]
    if not interrupts:
        raise ResumeNotPendingError("The run is not waiting for input.")
    payload = interrupts[0].value
    if len(interrupts) != 1 or not isinstance(payload, dict) or "kind" not in payload:
        raise CheckpointCorruptError("Checkpoint interrupt payload is malformed.")
    return payload["kind"], payload, checkpoint_id


def resume_pending(
    graph: Any,
    thread_id: str,
    *,
    expected_kind: str,
    expected_checkpoint_id: str | None,
    resume_value: Any,
    from_checkpoint_id: str | None = None,
) -> dict[str, Any]:
    """Resume only the exact interrupt the caller validated against.

    ``from_checkpoint_id`` forks from an earlier pause (rebuild from the DB);
    the original branch is left untouched.
    """
    kind, _, checkpoint_id = pending_interrupt(graph, thread_id, from_checkpoint_id)
    if kind != expected_kind or (
        expected_checkpoint_id is not None and checkpoint_id != expected_checkpoint_id
    ):
        raise ResumeConflictError(
            f"Run is waiting for '{kind}', not the requested step."
        )
    with map_checkpoint_errors(unreadable_is_corrupt=False):
        return graph.invoke(
            Command(resume=resume_value),
            config=thread_config(thread_id, from_checkpoint_id),
        )
