"""Qwen candidate explanations — never changes candidates, ranking, or confirmation.

The server computes every fact (attendance, who is missing, earliest/longest,
time of day, why rank 1 leads) plus pros/cons hints. Qwen only rewords them into
  - summary:    2 sentences ("{date} {time}을 추천합니다. {reason + attendance}")
  - comparison: per candidate (top 3) pros 1~2 / cons 0~2 short noun phrases
The output is cleaned (split words, spaces), then validated against the facts.
Any failure leaves ai_summary NULL; voting is unaffected.

Stored in schedule_runs.ai_summary as JSON {"v": 2, "summary", "comparison"}.
Read it back with parse_stored_summary() (plain text from older runs still works).
Prompt and few-shot are the ones that passed the live Qwen test (2026-11-28, prompt B).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta

from sqlalchemy import select

from db_v21.models.room import RoomMember
from db_v21.models.schedule import (
    ScheduleCandidate,
    ScheduleCandidateMember,
    ScheduleResponse,
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

STORE_VERSION = 2
MAX_COMPARE_CANDIDATES = 3
MAX_SUMMARY_CHARS = 160
MAX_ITEM_CHARS = 15
_COMMIT_WAIT_S = 2.0
_COMMIT_POLL_S = 0.05

_WEEKDAYS_KO = ("월", "화", "수", "목", "금", "토", "일")

_in_flight: set[str] = set()
_in_flight_guard = threading.Lock()

# Test hooks
_summary_client = None  # async (run_id, payload) -> raw model content (JSON string) | None
_background_enabled = True  # set False in suite setUp to avoid cross-test threads

# --- Prompt (verbatim from the passing live test) ----------------------------

SYSTEM_PROMPT = """너는 Potato Meet 일정 후보 설명 작성기다.
규칙:
- 입력의 facts는 서버가 이미 계산한 값이다. 순위·후보·인원을 바꾸거나 새로 만들지 않는다.
- summary: 한국어 2문장. 첫 문장은 "{1위 date} {1위 time}을 추천합니다." 형식. 둘째 문장은 rank_reason과 1위 attendance를 근거로 왜 1위인지 설명한다. 인원은 attendance 표현을 그대로 쓴다("N명 중 M명"을 "M명 모두"로 바꾸지 않는다). 후보가 1개면 둘째 문장에서 attendance를 설명한다.
- comparison: facts.candidates의 각 rank마다 하나. pros(장점) 1~2개, cons(고려 사항) 0~2개. 각 항목은 15자 이내 명사구.
- 숫자는 facts에 있는 값만 아라비아 숫자로 쓴다. 계산하거나 반올림하지 않는다.
- everyone_available이 false인 후보에 "전원 참석"을 쓰지 않는다. 시간대 표현은 그 후보의 time_of_day만 쓴다.
- 이메일, 마크다운, 추론 과정은 쓰지 않는다. JSON 객체 하나만 출력한다. /no_think
- 각 후보의 hints.pros / hints.cons를 재료로 자연스럽게 다듬는다. hints에 없는 사실은 추가하지 않는다."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "comparison": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "cons": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["rank", "pros", "cons"],
            },
        },
    },
    "required": ["summary", "comparison"],
}

# Few-shot: different dates/names from real data.
_EXAMPLE_PARTICIPANTS = ["하늘", "바다", "별"]
_EXAMPLE_CANDIDATES = [
    (datetime(2026, 10, 3, 13, 0, tzinfo=SEOUL), 120, ["하늘", "바다", "별"]),
    (datetime(2026, 10, 4, 19, 0, tzinfo=SEOUL), 180, ["하늘", "바다"]),
]
_EXAMPLE_ANSWER = {
    "summary": "10월 3일(토) 13:00~15:00을 추천합니다. 참여 가능 인원이 가장 많은 일정으로, 3명 모두 참석할 수 있어요.",
    "comparison": [
        {"rank": 1, "pros": ["전원 참석", "가장 빠른 일정"], "cons": ["2시간으로 짧음"]},
        {"rank": 2, "pros": ["3시간 확보"], "cons": ["별 불참", "저녁 시간대"]},
    ],
}

# --- Background job -----------------------------------------------------------


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
    payload = None
    while time.monotonic() < deadline:
        payload = _load_summary_input(run_id)
        if payload is not None:
            break
        await asyncio.sleep(_COMMIT_POLL_S)
    if payload is None or payload.get("already"):
        return

    stored: str | None = None
    try:
        if _summary_client is not None:
            raw = await _summary_client(run_id, payload)
        else:
            raw = await _generate(payload["facts"])
        if raw is not None:
            result = validate_output(raw, payload["facts"])
            stored = json.dumps(
                {"v": STORE_VERSION, **result}, ensure_ascii=False
            )
    except QwenBusy:
        logger.info("ai_summary skipped busy run_id=%s", run_id)
    except (QwenTimeout, QwenUnavailable, QwenInvalidResponse, ValueError):
        logger.info("ai_summary failed run_id=%s", run_id, exc_info=True)
    except Exception:
        logger.exception("ai_summary unexpected run_id=%s", run_id)

    _store_summary(run_id, stored)


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
        member_ids_by_candidate = {
            c.id: list(
                db.scalars(
                    select(ScheduleCandidateMember.room_member_id).where(
                        ScheduleCandidateMember.candidate_id == c.id
                    )
                ).all()
            )
            for c in candidates
        }
        # Participants = members who completed input for this run's collection.
        participant_ids = set(
            db.scalars(
                select(ScheduleResponse.room_member_id).where(
                    ScheduleResponse.collection_id == run.collection_id
                )
            ).all()
        )
        all_ids = participant_ids.union(*member_ids_by_candidate.values())
        nick_by_id = {
            m.id: m.nickname
            for m in db.scalars(
                select(RoomMember).where(RoomMember.id.in_(all_ids))
            ).all()
        }
        items = []
        for c in candidates:
            mids = member_ids_by_candidate[c.id]
            items.append(
                {
                    "rank": c.sort_order,
                    "starts_at": c.starts_at,
                    "ends_at": c.ends_at,
                    "nicknames": [nick_by_id[m] for m in mids if m in nick_by_id],
                }
            )
        participants = sorted(nick_by_id[m] for m in participant_ids if m in nick_by_id)
        if not participants:
            # Older runs without responses: fall back to everyone seen in candidates.
            participants = sorted({n for i in items for n in i["nicknames"]})
        return {"already": False, "facts": build_facts(items, participants)}


# --- Facts (pure) -------------------------------------------------------------


def _as_seoul(dt: datetime) -> datetime:
    return dt.astimezone(SEOUL) if dt.tzinfo else dt.replace(tzinfo=SEOUL)


def time_of_day(start: datetime) -> str:
    h = _as_seoul(start).hour
    if h < 5:
        return "새벽"
    if h < 9:
        return "이른 오전"
    if h < 12:
        return "오전"
    if h < 14:
        return "점심"
    if h < 18:
        return "오후"
    if h < 21:
        return "저녁"
    return "늦은 밤"


def duration_text(minutes: int) -> str:
    h, m = divmod(abs(minutes), 60)
    if h and m:
        return f"{h}시간 {m}분"
    return f"{h}시간" if h else f"{m}분"


def time_range(starts: datetime, ends: datetime) -> str:
    s, e = _as_seoul(starts), _as_seoul(ends)
    end = e.strftime("%H:%M")
    # Candidates are split at midnight, so an end of 00:00 the next day is 24:00.
    if e.date() > s.date() and e.hour == 0 and e.minute == 0:
        end = "24:00"
    return f"{s.strftime('%H:%M')}~{end}"


def date_label(dt: datetime) -> str:
    d = _as_seoul(dt)
    return f"{d.month}월 {d.day}일({_WEEKDAYS_KO[d.weekday()]})"


def rank_reason(first: dict, second: dict) -> str:
    """Why rank 1 leads under sort_order (count DESC → duration DESC → start ASC)."""
    if first["available_count"] > second["available_count"]:
        return "참여 가능 인원이 가장 많은 일정"
    if first["duration_minutes"] > second["duration_minutes"]:
        return "참여 인원이 같고 진행 시간이 더 긴 일정"
    return "참여 조건이 같아 더 빨리 진행할 수 있는 일정"


def hints(fact: dict) -> dict:
    """Pros/cons material decided by the server; Qwen only polishes the wording."""
    pros, cons = [], []
    missing = fact["missing_nicknames"]
    if fact["everyone_available"]:
        pros.append("전원 참석")
    else:
        names = ", ".join(missing) if len(missing) <= 2 else f"{len(missing)}명"
        cons.append(f"{names} 불참")
    if fact["is_earliest"]:
        pros.append("가장 빠른 일정")
    if fact["is_longest"]:
        pros.append(f"{fact['duration']} 확보")
    else:
        cons.append(f"{fact['duration']}으로 짧음")
    if fact["time_of_day"] in ("새벽", "이른 오전", "저녁", "늦은 밤"):
        cons.append(f"{fact['time_of_day']} 시간대")
    if not pros:
        pros.append(f"{fact['available_count']}명 참석 가능")
    return {"pros": pros[:2], "cons": cons[:2]}


def build_facts(items: list[dict], participants: list[str]) -> dict:
    """items: rank, starts_at, ends_at, nicknames — sorted by rank. Pure."""
    items = sorted(items, key=lambda i: i["rank"])
    top = items[:MAX_COMPARE_CANDIDATES]
    minutes_of = {
        i["rank"]: int((i["ends_at"] - i["starts_at"]) / timedelta(minutes=1)) for i in top
    }
    earliest = min(i["starts_at"] for i in top)
    longest = max(minutes_of.values())
    total = len(participants)
    out = []
    for i in top:
        minutes = minutes_of[i["rank"]]
        present = set(i["nicknames"])
        missing = [p for p in participants if p not in present]
        count = len(i["nicknames"])
        out.append(
            {
                "rank": i["rank"],
                "label": f"{i['rank']}위",
                "date": date_label(i["starts_at"]),
                "time": time_range(i["starts_at"], i["ends_at"]),
                "duration": duration_text(minutes),
                "duration_minutes": minutes,
                "available_count": count,
                "everyone_available": not missing,
                "missing_nicknames": missing,
                "time_of_day": time_of_day(i["starts_at"]),
                "attendance": f"{total}명 모두 참석" if not missing else f"{total}명 중 {count}명 참석",
                "is_earliest": i["starts_at"] == earliest,
                "is_longest": minutes == longest,
            }
        )
    for f in out[1:]:
        cd = f["available_count"] - out[0]["available_count"]
        dd = f["duration_minutes"] - out[0]["duration_minutes"]
        bits = [
            f"1위보다 {abs(cd)}명 {'많음' if cd > 0 else '적음'}" if cd else "1위와 인원 같음",
            f"{duration_text(dd)} 더 {'김' if dd > 0 else '짧음'}" if dd else "길이 같음",
        ]
        f["vs_first"] = ", ".join(bits)
    for f in out:
        f["hints"] = hints(f)
    facts = {"participant_count": total, "candidate_count": len(items), "candidates": out}
    if len(out) >= 2:
        facts["rank_reason"] = rank_reason(out[0], out[1])
    return facts


def _example_facts() -> dict:
    items = [
        {"rank": r, "starts_at": s, "ends_at": s + timedelta(minutes=m), "nicknames": who}
        for r, (s, m, who) in enumerate(_EXAMPLE_CANDIDATES, start=1)
    ]
    return build_facts(items, _EXAMPLE_PARTICIPANTS)


def messages_for(facts: dict) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps({"facts": _example_facts()}, ensure_ascii=False)},
        {"role": "assistant", "content": json.dumps(_EXAMPLE_ANSWER, ensure_ascii=False)},
        {"role": "user", "content": json.dumps({"facts": facts}, ensure_ascii=False)},
    ]


async def _generate(facts: dict) -> str:
    return await chat_completion(
        messages_for(facts),
        temperature=0,
        seed=42,
        max_tokens=400,
        response_format={"type": "json_object", "schema": OUTPUT_SCHEMA},
        skip_if_busy=True,
    )


# --- Clean + validate (pure) --------------------------------------------------

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_NATIVE_NUMBERS = {
    "열두": 12, "열한": 11, "열": 10, "아홉": 9, "여덟": 8, "일곱": 7, "여섯": 6,
    "다섯": 5, "네": 4, "세": 3, "두": 2, "한": 1, "스무": 20, "스물": 20,
}
_NATIVE_RE = re.compile(
    r"(?<![가-힣])(" + "|".join(sorted(_NATIVE_NUMBERS, key=len, reverse=True))
    + r")\s?(?=(?:명|사람|시간|시|개|번째|번|가지|후보|위))"
)
_SINO_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
# Only 십 compounds: single syllables (이, 일, 오…) collide with ordinary words.
_SINO_RE = re.compile(
    r"(?<![가-힣])([일이삼사오육칠팔구]?십[일이삼사오육칠팔구]?)\s?(?=(?:분|일|월|명|시간|위))"
)
_PUSH_PHRASES = ("투표하세요", "고르세요", "골라 보세요", "선택하세요", "선택해 보세요")
_TOD_WORDS = ("새벽", "아침", "오전", "점심", "낮", "오후", "저녁", "밤")
_TOD_ALLOWED = {
    "새벽": {"새벽"}, "이른 오전": {"아침", "오전"}, "오전": {"아침", "오전"},
    "점심": {"점심", "낮"}, "오후": {"오후", "낮"}, "저녁": {"저녁"}, "늦은 밤": {"밤", "저녁"},
}
# The 1.7B model sometimes splits words ("4시 간 확보"); re-join common ones.
_JOIN_WORDS = ("시간대", "시간", "참석", "불참", "확보", "일정", "짧음")
_JOIN_RES = [(re.compile(r"\s+".join(map(re.escape, w))), w) for w in _JOIN_WORDS]


def _korean_numbers_to_digits(text: str) -> str:
    out = _NATIVE_RE.sub(lambda m: str(_NATIVE_NUMBERS[m.group(1)]), text)

    def sino(m: re.Match) -> str:
        tens, _, ones = m.group(1).partition("십")
        return str(_SINO_DIGITS.get(tens, 1) * 10 + _SINO_DIGITS.get(ones, 0))

    out = _SINO_RE.sub(sino, out)
    return re.sub(r"(\d+)시간\s?반", lambda m: f"{m.group(1)}.5시간", out)


def _clean_text(text: str, *, join_words: bool) -> str:
    out = " ".join(text.split())
    out = re.sub(r"(\d)\s*시\s+간", r"\1시간", out)
    if join_words:
        for pattern, word in _JOIN_RES:
            out = pattern.sub(word, out)
    return out


def _norm_number(value) -> str:
    f = float(value)
    return str(int(f)) if f.is_integer() else f"{f:g}"


def _allowed_numbers(facts: dict) -> set[str]:
    first = facts["candidates"][0]
    nums: set = {facts["participant_count"], facts["candidate_count"], len(facts["candidates"])}
    for c in facts["candidates"]:
        nums |= {c["rank"], c["available_count"], len(c["missing_nicknames"])}
        nums.add(abs(c["available_count"] - first["available_count"]))
        nums |= {int(x) for x in _NUMBER_RE.findall(c["date"])}
        for x in _NUMBER_RE.findall(c["time"]):
            v = int(x)
            nums.add(v)
            if 13 <= v <= 24:
                nums.add(v - 12)  # 오후 2시
        for minutes in (c["duration_minutes"], abs(c["duration_minutes"] - first["duration_minutes"])):
            h, m = divmod(minutes, 60)
            nums |= {minutes, h, m}
            if m:
                nums.add(minutes / 60)  # 1.5시간
    return {_norm_number(n) for n in nums}


def validate_output(raw: str, facts: dict) -> dict:
    """Parse, clean and check the model output. Returns {"summary", "comparison"}.

    Raises ValueError on anything that disagrees with the facts.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("model output is not JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("model output is not an object")
    summary = data.get("summary")
    comp = data.get("comparison")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary missing")
    if not isinstance(comp, list):
        raise ValueError("comparison missing")

    summary = _clean_text(summary, join_words=False)
    by_rank = {c["rank"]: c for c in facts["candidates"]}
    first = facts["candidates"][0]

    day = first["date"].split("(")[0]  # "12월 1일"
    if day not in summary or first["time"] not in summary:
        raise ValueError("summary lacks rank-1 date/time")
    if not first["everyone_available"] and ("모두" in summary or "전원" in summary):
        raise ValueError("summary claims everyone for rank 1")
    if len(summary) > MAX_SUMMARY_CHARS:
        raise ValueError("summary too long")

    ranks = [item.get("rank") if isinstance(item, dict) else None for item in comp]
    if ranks != [c["rank"] for c in facts["candidates"]]:
        raise ValueError(f"comparison ranks {ranks}")

    cleaned_comp = []
    texts = [summary]
    for item in comp:
        fact = by_rank[item["rank"]]
        canon = {h.replace(" ", ""): h for h in fact["hints"]["pros"] + fact["hints"]["cons"]}
        out_item = {"rank": item["rank"]}
        for key in ("pros", "cons"):
            values = item.get(key)
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError(f"rank {item['rank']} {key} not a string list")
            cleaned = []
            for v in values:
                v = _clean_text(v, join_words=True)
                v = canon.get(v.replace(" ", ""), v)  # snap to server hint wording
                if v:
                    cleaned.append(v)
            out_item[key] = cleaned
        pros, cons = out_item["pros"], out_item["cons"]
        if not 1 <= len(pros) <= 2 or len(cons) > 2:
            raise ValueError(f"rank {item['rank']} item count")
        for t in pros + cons:
            if len(t) > MAX_ITEM_CHARS:
                raise ValueError(f"item too long: {t}")
            for w in _TOD_WORDS:
                if w in t and w not in _TOD_ALLOWED[fact["time_of_day"]]:
                    raise ValueError(f"wrong time of day: {t}")
        if not fact["everyone_available"] and any("전원" in p or "모두" in p for p in pros):
            raise ValueError(f"rank {item['rank']} claims everyone")
        if fact["is_longest"] and any("짧" in c for c in cons):
            raise ValueError(f"rank {item['rank']} longest called short")
        if not fact["is_earliest"] and any("가장 빠" in p for p in pros):
            raise ValueError(f"rank {item['rank']} not earliest")
        texts += pros + cons
        cleaned_comp.append(out_item)

    allowed = _allowed_numbers(facts)
    for t in texts:
        for n in _NUMBER_RE.findall(_korean_numbers_to_digits(t)):
            if _norm_number(n) not in allowed:
                raise ValueError(f"number not in facts: {n}")
        compact = t.replace(" ", "")
        if any(p.replace(" ", "") in compact for p in _PUSH_PHRASES):
            raise ValueError("pushes a vote choice")
        if "@" in t:
            raise ValueError("email-like text")
    return {"summary": summary, "comparison": cleaned_comp}


# --- Storage ------------------------------------------------------------------


def parse_stored_summary(raw: str | None) -> tuple[str | None, list[dict] | None]:
    """ai_summary column → (summary text, comparison list) for API responses.

    Comparison items use API naming: {"sortOrder", "pros", "cons"}.
    Plain text from runs before v2 is returned as the summary with no comparison.
    """
    if not raw:
        return None, None
    text = raw.strip()
    if not text.startswith("{"):
        return text, None
    try:
        data = json.loads(text)
    except ValueError:
        return None, None
    if not isinstance(data, dict) or not isinstance(data.get("summary"), str):
        return None, None
    comparison = []
    for item in data.get("comparison") or []:
        if not isinstance(item, dict) or not isinstance(item.get("rank"), int):
            continue
        comparison.append(
            {
                "sortOrder": item["rank"],
                "pros": [p for p in item.get("pros", []) if isinstance(p, str)],
                "cons": [c for c in item.get("cons", []) if isinstance(c, str)],
            }
        )
    return data["summary"], comparison or None


def _store_summary(run_id: str, stored: str | None) -> None:
    if stored is None:
        return
    room_id = None
    revision = None
    with session() as db, db.begin():
        run = db.get(ScheduleRun, run_id)
        if run is None or run.ai_summary is not None:
            return
        # Never rewrite ranking/candidates — only fill the explanation column.
        run.ai_summary = stored
        room_id = run.room_id
        from db_v21.models.room import Room

        room = db.get(Room, room_id)
        revision = room.revision if room else 0
    if room_id is not None:
        from schedule.events import publish_now

        publish_now(room_id, "ai_summary_ready", revision or 0)
