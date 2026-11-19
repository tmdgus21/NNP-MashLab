"""In-process SSE broadcaster (no DB outbox). Reconnect = client refetch APIs."""
from __future__ import annotations

import asyncio
import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# event names from architecture.md
EVENT_NAMES = frozenset(
    {
        "member_joined",
        "response_submitted",
        "collection_closed",
        "collection_opened",
        "coordinated",
        "ai_summary_ready",
        "readjust_opened",
        "grace_started",
        "voting_started",
        "vote_updated",
        "voting_closed",
        "confirmed",
        "meeting_deleted",
    }
)

_pending: ContextVar[list["PendingEvent"] | None] = ContextVar(
    "schedule_sse_pending", default=None
)


@dataclass(frozen=True)
class PendingEvent:
    room_id: str
    event: str
    revision: int
    extra: dict[str, Any]


class RoomHub:
    """Per-room fan-out via asyncio.Queue (single uvicorn worker)."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._guard = asyncio.Lock()

    async def subscribe(self, room_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        async with self._guard:
            self._subs.setdefault(room_id, set()).add(q)
        return q

    async def unsubscribe(self, room_id: str, q: asyncio.Queue) -> None:
        async with self._guard:
            bucket = self._subs.get(room_id)
            if not bucket:
                return
            bucket.discard(q)
            if not bucket:
                self._subs.pop(room_id, None)

    async def publish(self, room_id: str, event: str, payload: dict[str, Any]) -> None:
        async with self._guard:
            targets = list(self._subs.get(room_id, ()))
        for q in targets:
            try:
                q.put_nowait({"event": event, "data": payload})
            except asyncio.QueueFull:
                # Drop oldest-style: skip slow consumer; client will refetch on reconnect
                logger.warning("sse queue full room=%s event=%s", room_id, event)


hub = RoomHub()
_main_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """Called from FastAPI lifespan so sweep threads can publish."""
    global _main_loop
    _main_loop = loop


def queue_event(
    room_id: str,
    event: str,
    revision: int,
    **extra: Any,
) -> None:
    """Queue an event to publish after the current DB transaction commits."""
    if event not in EVENT_NAMES:
        raise ValueError(f"unknown sse event: {event}")
    pending = _pending.get()
    if pending is None:
        pending = []
        _pending.set(pending)
    pending.append(
        PendingEvent(room_id=room_id, event=event, revision=revision, extra=dict(extra))
    )


def drain_pending() -> list[PendingEvent]:
    pending = _pending.get()
    _pending.set(None)
    return list(pending or ())


def _dispatch(item: PendingEvent) -> None:
    payload = {"meetingId": item.room_id, "revision": item.revision, **item.extra}
    coro = hub.publish(item.room_id, item.event, payload)
    try:
        running = asyncio.get_running_loop()
        running.create_task(coro)
        return
    except RuntimeError:
        pass
    if _main_loop is not None and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, _main_loop)
        return
    coro.close()  # no loop (sync unit tests) — clients refetch on reconnect


def publish_pending_sync() -> None:
    """Schedule async publishes onto the app loop (after commit)."""
    for item in drain_pending():
        _dispatch(item)


def publish_now(room_id: str, event: str, revision: int, **extra: Any) -> None:
    """Publish immediately (e.g. after a background AI write commits)."""
    if event not in EVENT_NAMES:
        return
    _dispatch(
        PendingEvent(room_id=room_id, event=event, revision=revision, extra=dict(extra))
    )


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
