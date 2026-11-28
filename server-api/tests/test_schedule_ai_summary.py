"""Qwen schedule summary — fake client only; ranking/confirm unchanged."""
from __future__ import annotations

import json
import os
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_ENABLED"] = "0"

import database as database_module

database_module._engine = None

from sqlalchemy import select

from database import initialize, session
from db_v21.base import uid
from db_v21.models.account import Account
from db_v21.models.room import Room, RoomMember
from db_v21.models.schedule import (
    ScheduleCandidate,
    ScheduleCandidateMember,
    ScheduleCollection,
    ScheduleRun,
)
from qwen_client import QwenBusy, QwenTimeout
from schedule import ai_summary as summary_mod
from schedule.constants import SEOUL


def _seed_run_with_candidates(*, summary=None):
    with session() as db, db.begin():
        a1 = Account(
            id=uid(),
            login_email=f"{uid()[:8]}@example.test",
            password_hash="x",
        )
        a2 = Account(
            id=uid(),
            login_email=f"{uid()[:8]}@example.test",
            password_hash="x",
        )
        db.add(a1)
        db.add(a2)
        db.flush()
        now = datetime.now(SEOUL)
        room = Room(
            id=uid(),
            code=uid()[:8],
            title="요약테스트",
            starts_at=now,
            ends_at=now + timedelta(days=2),
            progress_status="reviewing",
            lifecycle_status="WAITING_FOR_CONSENT",
            revision=1,
        )
        db.add(room)
        db.flush()
        owner = RoomMember(
            id=uid(),
            room_id=room.id,
            account_id=a1.id,
            nickname="감자",
            room_role="OWNER",
        )
        other = RoomMember(
            id=uid(),
            room_id=room.id,
            account_id=a2.id,
            nickname="고구마",
            room_role="MEMBER",
        )
        db.add(owner)
        db.add(other)
        db.flush()
        room.host_member_id = owner.id
        col = ScheduleCollection(
            id=uid(),
            room_id=room.id,
            cycle=0,
            kind="NORMAL",
            scope_starts_at=now,
            scope_ends_at=now + timedelta(days=1),
            closes_at=now,
            status="CLOSED",
        )
        db.add(col)
        db.flush()
        run = ScheduleRun(
            id=uid(),
            room_id=room.id,
            collection_id=col.id,
            max_count=2,
            participant_count=2,
            voter_count=2,
            ai_summary=summary,
            created_at=now,
        )
        db.add(run)
        db.flush()
        start = now + timedelta(hours=4)
        end = start + timedelta(hours=2)
        c1 = ScheduleCandidate(
            id=uid(),
            run_id=run.id,
            room_id=room.id,
            starts_at=start,
            ends_at=end,
            available_count=2,
            sort_order=1,
        )
        c2 = ScheduleCandidate(
            id=uid(),
            run_id=run.id,
            room_id=room.id,
            starts_at=start + timedelta(hours=1),
            ends_at=end + timedelta(hours=1),
            available_count=2,
            sort_order=2,
        )
        db.add(c1)
        db.add(c2)
        db.flush()
        for c in (c1, c2):
            db.add(
                ScheduleCandidateMember(
                    candidate_id=c.id, room_member_id=owner.id
                )
            )
            db.add(
                ScheduleCandidateMember(
                    candidate_id=c.id, room_member_id=other.id
                )
            )
        return run.id, c1.id, c2.id




def _good_answer(facts: dict, *, mutate=None) -> str:
    """What a well-behaved Qwen returns: summary + hints reworded as-is."""
    first = facts["candidates"][0]
    answer = {
        "summary": f"{first['date']} {first['time']}을 추천합니다. "
        f"{facts.get('rank_reason', '참여 가능한 일정')}으로, {first['attendance']}할 수 있어요.",
        "comparison": [
            {"rank": c["rank"], "pros": list(c["hints"]["pros"]), "cons": list(c["hints"]["cons"])}
            for c in facts["candidates"]
        ],
    }
    if mutate:
        mutate(answer)
    return json.dumps(answer, ensure_ascii=False)


class ScheduleAiSummaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "sqlite://"
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()
        initialize()
        summary_mod._summary_client = None
        summary_mod._background_enabled = True
        with summary_mod._in_flight_guard:
            summary_mod._in_flight.clear()

    def tearDown(self):
        summary_mod._summary_client = None
        summary_mod._background_enabled = True
        previous = database_module._engine
        database_module._engine = None
        if previous is not None:
            previous.dispose()

    def _stored(self, run_id):
        with session() as db:
            return db.get(ScheduleRun, run_id).ai_summary

    def _assert_candidates_intact(self, run_id, c1, c2):
        with session() as db:
            cands = list(
                db.scalars(
                    select(ScheduleCandidate)
                    .where(ScheduleCandidate.run_id == run_id)
                    .order_by(ScheduleCandidate.sort_order)
                )
            )
            self.assertEqual([c1, c2], [c.id for c in cands])
            self.assertEqual([1, 2], [c.sort_order for c in cands])
            self.assertEqual([2, 2], [c.available_count for c in cands])

    async def test_fills_summary_and_comparison(self):
        run_id, c1, c2 = _seed_run_with_candidates()

        async def fake(_run_id, payload):
            facts = payload["facts"]
            self.assertEqual(2, len(facts["candidates"]))
            self.assertEqual(
                "참여 조건이 같아 더 빨리 진행할 수 있는 일정", facts["rank_reason"]
            )
            self.assertEqual("2명 모두 참석", facts["candidates"][0]["attendance"])
            self.assertEqual(["전원 참석", "가장 빠른 일정"], facts["candidates"][0]["hints"]["pros"])
            return _good_answer(facts)

        summary_mod._summary_client = fake
        await summary_mod.fill_ai_summary(run_id)

        summary, comparison = summary_mod.parse_stored_summary(self._stored(run_id))
        self.assertIn("을 추천합니다.", summary)
        self.assertEqual([1, 2], [c["sortOrder"] for c in comparison])
        self.assertEqual(["전원 참석", "가장 빠른 일정"], comparison[0]["pros"])
        self._assert_candidates_intact(run_id, c1, c2)

    async def test_split_words_are_cleaned(self):
        run_id, _, _ = _seed_run_with_candidates()

        def split(answer):
            answer["comparison"][1]["pros"] = ["전원 참석", "2 시 간 확보"]

        async def fake(_run_id, payload):
            return _good_answer(payload["facts"], mutate=split)

        summary_mod._summary_client = fake
        await summary_mod.fill_ai_summary(run_id)
        _, comparison = summary_mod.parse_stored_summary(self._stored(run_id))
        self.assertEqual(["전원 참석", "2시간 확보"], comparison[1]["pros"])

    async def test_timeout_leaves_null_and_candidates_intact(self):
        run_id, c1, c2 = _seed_run_with_candidates()

        async def boom(_run_id, _payload):
            raise QwenTimeout()

        summary_mod._summary_client = boom
        await summary_mod.fill_ai_summary(run_id)
        self.assertIsNone(self._stored(run_id))
        self._assert_candidates_intact(run_id, c1, c2)

    async def test_busy_skips_without_writing(self):
        run_id, _, _ = _seed_run_with_candidates()

        async def busy(_run_id, _payload):
            raise QwenBusy()

        summary_mod._summary_client = busy
        await summary_mod.fill_ai_summary(run_id)
        self.assertIsNone(self._stored(run_id))

    async def test_rejected_outputs_leave_null(self):
        bad = {
            "not json": lambda f: "두 후보 모두 좋아요.",
            "invented number": lambda f: _good_answer(
                f, mutate=lambda a: a.update(summary=a["summary"] + " 99명이 기다려요.")
            ),
            "longest called short": lambda f: _good_answer(
                f, mutate=lambda a: a["comparison"][0]["cons"].append("2시간으로 짧음")
            ),
            "missing rank": lambda f: _good_answer(
                f, mutate=lambda a: a["comparison"].pop()
            ),
            "push vote": lambda f: _good_answer(
                f, mutate=lambda a: a.update(summary=a["summary"] + " 1위에 투표하세요.")
            ),
            "wrong time of day": lambda f: _good_answer(
                f,
                mutate=lambda a: a["comparison"][0]["cons"].append(
                    "새벽 시간대"
                    if f["candidates"][0]["time_of_day"] != "새벽"
                    else "저녁 시간대"
                ),
            ),
        }
        for name, make in bad.items():
            with self.subTest(name):
                run_id, _, _ = _seed_run_with_candidates()

                async def fake(_run_id, payload, make=make):
                    return make(payload["facts"])

                summary_mod._summary_client = fake
                await summary_mod.fill_ai_summary(run_id)
                self.assertIsNone(self._stored(run_id))

    def test_enqueue_dedupes_inflight(self):
        run_id, _, _ = _seed_run_with_candidates()
        gate = {"go": False, "entered": False}

        async def slow(_run_id, payload):
            gate["entered"] = True
            while not gate["go"]:
                await __import__("asyncio").sleep(0.01)
            return _good_answer(payload["facts"])

        summary_mod._summary_client = slow
        summary_mod.enqueue_ai_summary(run_id)
        for _ in range(200):
            if gate["entered"]:
                break
            time.sleep(0.01)
        self.assertTrue(gate["entered"])
        summary_mod.enqueue_ai_summary(run_id)
        with summary_mod._in_flight_guard:
            self.assertEqual({run_id}, summary_mod._in_flight)
        gate["go"] = True
        for _ in range(200):
            with summary_mod._in_flight_guard:
                if run_id not in summary_mod._in_flight:
                    break
            time.sleep(0.01)
        self.assertIsNotNone(self._stored(run_id))

    async def test_chat_completion_path_mocked(self):
        run_id, _, _ = _seed_run_with_candidates()
        seen = {}

        async def fake_chat(messages, **kwargs):
            seen["messages"] = messages
            seen["kwargs"] = kwargs
            facts = json.loads(messages[-1]["content"])["facts"]
            return _good_answer(facts)

        with patch.object(summary_mod, "chat_completion", fake_chat):
            await summary_mod.fill_ai_summary(run_id)
        self.assertEqual(summary_mod.SYSTEM_PROMPT, seen["messages"][0]["content"])
        self.assertEqual("assistant", seen["messages"][2]["role"])  # few-shot
        self.assertEqual("json_object", seen["kwargs"]["response_format"]["type"])
        self.assertEqual(0, seen["kwargs"]["temperature"])
        self.assertIsNotNone(self._stored(run_id))


class FactsAndValidationTests(unittest.TestCase):
    """Pure helpers — no DB. Outputs are the real Qwen answers from 2026-11-28."""

    def _facts(self, participants, cands):
        items = []
        for rank, (start, minutes, who) in enumerate(cands, start=1):
            items.append(
                {
                    "rank": rank,
                    "starts_at": start,
                    "ends_at": start + timedelta(minutes=minutes),
                    "nicknames": who,
                }
            )
        return summary_mod.build_facts(items, participants)

    def _same_conditions(self):
        return self._facts(
            ["감자", "고구마"],
            [
                (datetime(2026, 12, 1, 18, 0, tzinfo=SEOUL), 120, ["감자", "고구마"]),
                (datetime(2026, 12, 2, 8, 0, tzinfo=SEOUL), 120, ["감자", "고구마"]),
            ],
        )

    def _big_group(self):
        everyone = ["감자", "고구마", "옥수수", "당근", "양파", "마늘", "배추", "무"]
        return self._facts(
            everyone,
            [
                (datetime(2026, 12, 10, 19, 0, tzinfo=SEOUL), 120, everyone[:7]),
                (datetime(2026, 12, 11, 12, 0, tzinfo=SEOUL), 180, everyone[:6]),
            ],
        )

    def test_facts_same_conditions(self):
        facts = self._same_conditions()
        first, second = facts["candidates"]
        self.assertEqual("12월 1일(화)", first["date"])
        self.assertEqual("18:00~20:00", first["time"])
        self.assertEqual("저녁", first["time_of_day"])
        self.assertEqual("이른 오전", second["time_of_day"])
        self.assertEqual("참여 조건이 같아 더 빨리 진행할 수 있는 일정", facts["rank_reason"])
        self.assertEqual({"pros": ["전원 참석", "가장 빠른 일정"], "cons": ["저녁 시간대"]}, first["hints"])
        self.assertEqual({"pros": ["전원 참석", "2시간 확보"], "cons": ["이른 오전 시간대"]}, second["hints"])

    def test_facts_big_group(self):
        facts = self._big_group()
        first, second = facts["candidates"]
        self.assertEqual("8명 중 7명 참석", first["attendance"])
        self.assertEqual(["무"], first["missing_nicknames"])
        self.assertEqual("배추, 무 불참", second["hints"]["cons"][0])
        self.assertEqual("참여 가능 인원이 가장 많은 일정", facts["rank_reason"])

    def test_top_three_only(self):
        base = datetime(2026, 12, 1, 15, 0, tzinfo=SEOUL)
        facts = self._facts(
            ["감자", "고구마"],
            [(base + timedelta(days=d), 60, ["감자", "고구마"]) for d in range(4)],
        )
        self.assertEqual(4, facts["candidate_count"])
        self.assertEqual([1, 2, 3], [c["rank"] for c in facts["candidates"]])

    def test_midnight_end_shows_24(self):
        start = datetime(2026, 12, 5, 21, 0, tzinfo=SEOUL)
        self.assertEqual("21:00~24:00", summary_mod.time_range(start, start + timedelta(hours=3)))

    def test_real_qwen_output_prompt_b_passes(self):
        raw = (
            '{"summary": "12월 1일(화) 18:00~20:00을 추천합니다. 참여 조건이 같아 빠르게 진행할 수 있어요.", '
            '"comparison": [{"rank": 1, "pros": ["전원 참석", "가장 빠른 일정"], "cons": ["저녁 시간대"]}, '
            '{"rank": 2, "pros": ["전원 참석", "2시간 확보"], "cons": ["이른 오전 시간대"]}]}'
        )
        result = summary_mod.validate_output(raw, self._same_conditions())
        self.assertEqual(["저녁 시간대"], result["comparison"][0]["cons"])

    def test_real_qwen_output_prompt_a_rejected(self):
        # Prompt A copied the few-shot "2시간으로 짧음" onto the longest candidate.
        raw = (
            '{"summary": "12월 1일(화) 18:00~20:00을 추천합니다. 참여 조건이 같아 빠르게 진행할 수 있어요.", '
            '"comparison": [{"rank": 1, "pros": ["전원 참석", "가장 빠른 일정"], "cons": ["2시간으로 짧음"]}, '
            '{"rank": 2, "pros": ["2시간 확보"], "cons": [" 이른 오전 시간대"]}]}'
        )
        with self.assertRaises(ValueError):
            summary_mod.validate_output(raw, self._same_conditions())

    def test_real_qwen_output_all_claim_rejected(self):
        raw = (
            '{"summary": "12월 10일(목) 19:00~21:00을 추천합니다. 참여 가능 인원이 가장 많은 일정이라 7명 모두 함께할 수 있어요.", '
            '"comparison": [{"rank": 1, "pros": ["가장 빠른 일정"], "cons": ["무 불참", "2시간으로 짧음"]}, '
            '{"rank": 2, "pros": ["3시간 확보"], "cons": ["배추, 무 불참"]}]}'
        )
        with self.assertRaises(ValueError):
            summary_mod.validate_output(raw, self._big_group())

    def test_real_qwen_output_split_word_cleaned(self):
        raw = (
            '{"summary": "12월 10일(목) 19:00~21:00을 추천합니다. 참여 가능 인원이 가장 많은 일정으로, 8명 중 7명 참석할 수 있어요.", '
            '"comparison": [{"rank": 1, "pros": ["가장 빠른 일정"], "cons": ["무 불참", "2시간으로 짧음"]}, '
            '{"rank": 2, "pros": ["3 시간 확보"], "cons": ["배추, 무 불참"]}]}'
        )
        result = summary_mod.validate_output(raw, self._big_group())
        self.assertEqual(["3시간 확보"], result["comparison"][1]["pros"])

    def test_korean_number_words(self):
        conv = summary_mod._korean_numbers_to_digits
        self.assertEqual("3명 모두", conv("세 명 모두"))
        self.assertEqual("1.5시간", conv("한 시간 반"))
        self.assertEqual("30분", conv("삼십 분"))
        self.assertEqual("이 시간이 좋아요", conv("이 시간이 좋아요"))

    def test_parse_stored_summary(self):
        self.assertEqual((None, None), summary_mod.parse_stored_summary(None))
        # Runs stored before v2 were plain text.
        self.assertEqual(("옛 요약 문장", None), summary_mod.parse_stored_summary("옛 요약 문장"))
        self.assertEqual((None, None), summary_mod.parse_stored_summary("{broken"))
        stored = json.dumps(
            {"v": 2, "summary": "요약", "comparison": [{"rank": 1, "pros": ["전원 참석"], "cons": []}]},
            ensure_ascii=False,
        )
        self.assertEqual(
            ("요약", [{"sortOrder": 1, "pros": ["전원 참석"], "cons": []}]),
            summary_mod.parse_stored_summary(stored),
        )
        # Account deletion scrubs nicknames by plain replace; JSON must stay readable.
        scrubbed = stored.replace("요약", "탈퇴한 사용자")
        self.assertEqual("탈퇴한 사용자", summary_mod.parse_stored_summary(scrubbed)[0])


if __name__ == "__main__":
    unittest.main()
