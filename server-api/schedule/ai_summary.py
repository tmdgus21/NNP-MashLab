"""Qwen candidate explanations — never changes candidates, ranking, or confirmation."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime

from sqlalchemy import select

from db_v21.models.room import RoomMember
from db_v21.models.schedule import (
    ScheduleCandidate,
    ScheduleCandidateMember,
    ScheduleRun,
)
from database import session
from qwen_client import (
    QwenBusy,
    QwenInvalidResponse,
    QwenTimeout,
    QwenUnavailable,
    chat_completion,
)
from schedule.constants import SEOUL

logger = logging.getLogger(__name__)

MAX_SUMMARY_CHARS = 200
_COMMIT_WAIT_S = 2.0
_COMMIT_POLL_S = 0.05

_in_flight: set[str] = set()
_in_flight_guard = threading.Lock()

# Test hooks
_summary_client = None  # async (run_id, payload) -> str | None
_background_enabled = True  # set False in suite setUp to avoid cross-test threads

SYSTEM_PROMPT = """너는 Potato Meet 모임 후보 설명 작성기다.
서버가 이미 계산한 후보 목록만 설명한다. 새 후보·순위·인원·확정을 제안하거나 바꾸지 않는다.
한국어로 1~2문장만 출력한다. 최대 200자. 마크다운·목록·따옴표·이메일·추론 과정은 쓰지 않는다.
참가 가능 인원, 날짜·시간, 추천 순위(정렬 순서)를 자연스럽게 언급한다. /no_think"""


def enqueue_ai_summary(run_id: str) -> None:
    """Schedule background fill after the caller commits. Never blocks the API."""
    if not run_id or not _background_enabled:
        return
    with _in_flight_guard:
        if run_id in _in_flight:
            return
        _in_flight.add(run_id)

    def worker() -> None:
        try:
            asyncio.run(fill_ai_summary(run_id))
        except Exception:
            logger.exception("ai_summary worker failed run_id=%s", run_id)
        finally:
            with _in_flight_guard:
                _in_flight.discard(run_id)

    threading.Thread(target=worker, name=f"ai-summary-{run_id[:8]}", daemon=True).start()


async def fill_ai_summary(run_id: str) -> None:
    """Load run+candidates, call Qwen, store ai_summary or leave NULL on any failure."""
    deadline = time.monotonic() + _COMMIT_WAIT_S
    run_payload = None
    while time.monotonic() < deadline:
        run_payload = _load_summary_input(run_id)
        if run_payload is not None:
            break
        await asyncio.sleep(_COMMIT_POLL_S)
    if run_payload is None:
        return
    if run_payload.get("already"):
        return

    text: str | None = None
    try:
        if _summary_client is not None:
            text = await _summary_client(run_id, run_payload)
        else:
            text = await _generate_summary(run_payload)
        text = _normalize_summary(text)
    except QwenBusy:
        logger.info("ai_summary skipped busy run_id=%s", run_id)
        text = None
    except (QwenTimeout, QwenUnavailable, QwenInvalidResponse, ValueError):
        logger.info("ai_summary failed run_id=%s", run_id, exc_info=True)
        text = None
    except Exception:
        logger.exception("ai_summary unexpected run_id=%s", run_id)
        text = None

    _store_summary(run_id, text)


def _load_summary_input(run_id: str) -> dict | None:
    with session() as db:
        run = db.get(ScheduleRun, run_id)
        if run is None:
            return None
        if run.ai_summary is not None:
            return {"already": True}
        candidates = list(
            db.scalars(
                select(ScheduleCandidate)
                .where(ScheduleCandidate.run_id == run_id)
                .order_by(ScheduleCandidate.sort_order)
            ).all()
        )
        if not candidates:
            return {"already": True}
        member_ids = {
            mid
            for mid in db.scalars(
                select(ScheduleCandidateMember.room_member_id).where(
                    ScheduleCandidateMember.candidate_id.in_([c.id for c in candidates])
                )
            ).all()
        }
        nick_by_id = {
            m.id: m.nickname
            for m in db.scalars(
                select(RoomMember).where(RoomMember.id.in_(member_ids))
            ).all()
        }
        items = []
        for c in candidates:
            mids = list(
                db.scalars(
                    select(ScheduleCandidateMember.room_member_id).where(
                        ScheduleCandidateMember.candidate_id == c.id
                    )
                ).all()
            )
            items.append(
                {
                    "rank": c.sort_order,
                    "available_count": c.available_count,
                    "starts_at": _fmt_local(c.starts_at),
                    "ends_at": _fmt_local(c.ends_at),
                    "nicknames": [nick_by_id[m] for m in mids if m in nick_by_id],
                }
            )
        return {
            "already": False,
            "participant_count": run.participant_count,
            "candidates": items,
        }


async def _generate_summary(payload: dict) -> str:
    user = {
        "participant_count": payload["participant_count"],
        "candidates": payload["candidates"],
    }
    content = await chat_completion(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(user, ensure_ascii=False),
            },
        ],
        temperature=0.2,
        seed=None,
        max_tokens=256,
        response_format=None,
        skip_if_busy=True,
    )
    return content


def _normalize_summary(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return None
    if len(cleaned) > MAX_SUMMARY_CHARS:
        cleaned = cleaned[:MAX_SUMMARY_CHARS].rstrip()
    # Reject obvious non-prose dumps
    if cleaned.startswith("{") or cleaned.startswith("```"):
        raise ValueError("non-prose summary")
    return cleaned


def _store_summary(run_id: str, text: str | None) -> None:
    if text is None:
        return
    room_id = None
    revision = None
    with session() as db, db.begin():
        run = db.get(ScheduleRun, run_id)
        if run is None or run.ai_summary is not None:
            return
        # Never rewrite ranking/candidates — only fill the explanation column.
        run.ai_summary = text
        room_id = run.room_id
        from db_v21.models.room import Room

        room = db.get(Room, room_id)
        revision = room.revision if room else 0
    if room_id is not None:
        from schedule.events import publish_now

        publish_now(room_id, "ai_summary_ready", revision or 0)


def _fmt_local(dt: datetime) -> str:
    local = dt.astimezone(SEOUL) if dt.tzinfo else dt.replace(tzinfo=SEOUL)
    return local.strftime("%Y-%m-%d %H:%M")
