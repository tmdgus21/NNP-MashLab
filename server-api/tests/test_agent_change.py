"""Natural-language change proposal flow: service + HTTP tests (fake Qwen, SQLite)."""
from __future__ import annotations

import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ADMIN_ENABLED", "0")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db_v21.models.agent import AgentChangeProposal, AgentRun  # noqa: E402
from db_v21.models.condition import ConditionSubmission  # noqa: E402
from db_v21.models.room import Room, RoomMember  # noqa: E402
from potato_agent.llama_cpp import LlamaCppConfig, LlamaCppError, build_proposal_agent  # noqa: E402
from potato_agent.qwen_proposals import (  # noqa: E402
    ProposalValidationError,
    RescheduleIntentExtraction,
    build_proposal_from_intents,
)
from services import agent_change as ac  # noqa: E402
from services import agent_decision as ad  # noqa: E402
from services.agent_worker import claim_next_agent_run, execute_agent_run  # noqa: E402
from tests.test_agent_decision import DecisionBase  # noqa: E402

TODAY = date(2026, 11, 1)
HOST, MEMBER, OTHER = "account-host", "account-member", "account-no-submission"


class FakeQwen:
    """Stands in for Qwen at the Intent level so the REAL Validator runs."""

    def __init__(self, intents=(), ambiguities=(), summary="요약", before=None, raises=None):
        self.intents, self.ambiguities, self.summary = intents, ambiguities, summary
        self.before, self.raises = before, raises
        self.calls = 0

    def __call__(self, snapshot):
        self.snapshot = snapshot
        return self

    def propose(self, text, snapshot, actor, *, today=None):
        self.calls += 1
        if self.before:
            self.before()
        if self.raises:
            raise self.raises
        extraction = RescheduleIntentExtraction.model_validate({
            "base_input_revision": snapshot.input_revision,
            "intents": list(self.intents),
            "ambiguities": list(self.ambiguities),
            "summary": self.summary,
        })
        return build_proposal_from_intents(snapshot, actor, extraction, today=today)


DURATION_90 = {"kind": "SET_DURATION", "duration_minutes": 90}
DURATION_45 = {"kind": "SET_DURATION", "duration_minutes": 45}


class ChangeBase(DecisionBase):
    def setUp(self) -> None:
        super().setUp()
        self.open_sessions = 0
        base = self.factory

        def tracked():
            outer = self

            class S(Session):
                def __enter__(s):
                    outer.open_sessions += 1
                    return super().__enter__()

                def __exit__(s, *a):
                    outer.open_sessions -= 1
                    return super().__exit__(*a)

            return S(self.engine)

        self.tracked = tracked
        self.addCleanup(setattr, ac, "agent_factory", ac.agent_factory)

    def use(self, fake: FakeQwen) -> FakeQwen:
        ac.agent_factory = fake
        return fake

    def propose(self, actor=HOST, key="k1", text="회의 시간을 90분으로", **kw):
        return ac.create_change_proposal(
            self.tracked, room_id="room-1", actor_account_id=actor,
            idempotency_key=key, request_text=text, today=TODAY, **kw,
        )

    def approve(self, record, actor=HOST):
        return ac.approve_change_proposal(
            self.factory, room_id="room-1", proposal_id=record.id,
            actor_account_id=actor, today=TODAY,
        )

    def room(self) -> Room:
        with Session(self.engine) as db:
            room = db.get(Room, "room-1")
            db.expunge(room)
            return room

    def proposal_row(self, pid) -> AgentChangeProposal:
        with Session(self.engine) as db:
            row = db.get(AgentChangeProposal, pid)
            db.expunge(row)
            return row


class ProposeTests(ChangeBase):
    def test_proposal_never_changes_input_and_holds_no_session_during_qwen(self) -> None:
        seen = []
        fake = self.use(FakeQwen([DURATION_90], before=lambda: seen.append(self.open_sessions)))
        before = self.room()
        record = self.propose()
        self.assertEqual(seen, [0])  # no DB session open while Qwen ran
        self.assertEqual(record.status, "PROPOSED")
        after = self.room()
        self.assertEqual(
            (after.agent_input_revision, after.revision, after.meeting_settings),
            (before.agent_input_revision, before.revision, before.meeting_settings),
        )
        self.assertEqual(self._row(self.run_id).status, "ALL_AVAILABLE")
        self.assertEqual(fake.calls, 1)

    def test_idempotent_create_calls_qwen_once(self) -> None:
        fake = self.use(FakeQwen([DURATION_90]))
        first, again = self.propose(), self.propose()
        self.assertEqual((first.id, again.id, again.changed, fake.calls), (first.id, first.id, False, 1))
        with self.assertRaises(ac.IdempotencyKeyReusedError):
            self.propose(text="다른 요청")

    def test_only_host_may_change_meeting_constraints(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        with self.assertRaises(ac.InvalidProposalError) as raised:
            self.propose(actor=MEMBER)
        self.assertEqual(raised.exception.code, "HOST_REQUIRED")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(AgentChangeProposal.id)), None)

    def test_qwen_failures_are_typed_and_store_nothing(self) -> None:
        self.use(FakeQwen(raises=LlamaCppError("QWEN_TIMEOUT", "slow")))
        with self.assertRaises(ac.QwenUnavailableError):
            self.propose()
        self.use(FakeQwen(raises=ProposalValidationError("INVALID_MODEL_OUTPUT", "bad json")))
        with self.assertRaises(ac.InvalidProposalError) as raised:
            self.propose(key="k2")
        self.assertEqual(raised.exception.code, "INVALID_MODEL_OUTPUT")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(AgentChangeProposal.id)), None)

    def test_ambiguous_request_needs_clarification_and_cannot_be_approved(self) -> None:
        self.use(FakeQwen([], ["어느 날짜인지 알려 주세요."]))
        record = self.propose()
        self.assertEqual(record.status, "CLARIFICATION_REQUIRED")
        with self.assertRaises(ac.ProposalNotApprovableError):
            self.approve(record)

    def test_revision_change_during_qwen_call_discards_the_proposal(self) -> None:
        def bump():
            with Session(self.engine) as db:
                db.get(Room, "room-1").agent_input_revision = 9
                db.commit()

        self.use(FakeQwen([DURATION_90], before=bump))
        with self.assertRaises(ac.StaleProposalError):
            self.propose()
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(AgentChangeProposal.id)), None)

    def test_real_client_refuses_the_production_qwen_port(self) -> None:
        with self.assertRaises(ValueError):
            build_proposal_agent(
                self.use(FakeQwen()).snapshot if False else _any_snapshot(self),
                config=LlamaCppConfig(base_url="http://127.0.0.1:8080"),
            )


def _any_snapshot(test: ChangeBase):
    with Session(test.engine) as db:
        from services.meeting_snapshot import build_meeting_snapshot

        return build_meeting_snapshot(
            db, room_id="room-1", agent_session_id="s", run_id="r", consent_round=1
        )


class ApproveTests(ChangeBase):
    def test_approval_applies_bumps_revision_stales_old_work_and_queues_recompute(self) -> None:
        # a decision is already under way on the old Run
        ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                            actor_account_id=HOST, candidate_id=self.cid)
        self.consent(HOST)
        self.use(FakeQwen([DURATION_45]))
        record = self.propose()

        applied = self.approve(record)
        self.assertEqual((applied.status, applied.applied_revision, applied.changed), ("APPLIED", 6, True))
        room = self.room()
        self.assertEqual(room.agent_input_revision, 6)
        self.assertEqual(room.meeting_settings["coordination"]["durationMinutes"], 45)
        old = self._row(self.run_id)
        self.assertEqual((old.status, old.error_code), ("STALE", "STALE_AGENT_RUN"))
        with self.assertRaises(ad.RunNotDecidableError):  # old consent/approval can never continue
            self.consent(MEMBER)
        new = self._row(applied.resulting_run_id)
        self.assertEqual((new.status, new.source_revision), ("QUEUED", 6))
        self.assertNotEqual(new.input_snapshot_hash, old.input_snapshot_hash)

        # the existing Worker recomputes with CP-SAT on the approved input
        claim = claim_next_agent_run(self.factory, worker_id="w2", lease_seconds=30)
        self.assertEqual(claim.run.run_id, applied.resulting_run_id)
        result = execute_agent_run(claim, self.factory, lease_seconds=30, checkpointer=self.saver)
        self.assertEqual(result.status, "ALL_AVAILABLE")
        candidate = result.candidates[0].candidate
        self.assertEqual(candidate.end_minute - candidate.start_minute, 45)

    def test_duplicate_approval_is_idempotent(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        record = self.propose()
        first, second = self.approve(record), self.approve(record)
        self.assertEqual((second.changed, second.resulting_run_id), (False, first.resulting_run_id))
        self.assertEqual(self.room().agent_input_revision, 6)
        with Session(self.engine) as db:
            runs = list(db.scalars(select(AgentRun).where(AgentRun.status == "QUEUED")))
        self.assertEqual(len(runs), 1)

    def test_only_the_requester_may_approve(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        record = self.propose()
        with self.assertRaises(ac.ProposalForbiddenError):
            self.approve(record, actor=MEMBER)
        self.assertEqual(self.room().agent_input_revision, 5)

    def test_concurrent_edit_supersedes_the_proposal_and_changes_nothing(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        record = self.propose()
        with Session(self.engine) as db:  # someone else edits the meeting first
            room = db.get(Room, "room-1")
            room.agent_input_revision = 6
            db.commit()
        with self.assertRaises(ac.StaleProposalError):
            self.approve(record)
        self.assertEqual(self.proposal_row(record.id).status, "SUPERSEDED")
        self.assertEqual(self.room().meeting_settings["coordination"]["durationMinutes"], 60)
        with self.assertRaises(ac.ProposalNotApprovableError):
            self.approve(record)

    def test_changed_hash_without_revision_bump_is_also_stale(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        record = self.propose()
        with Session(self.engine) as db:
            room = db.get(Room, "room-1")
            settings = dict(room.meeting_settings)
            settings["coordination"] = {**settings["coordination"], "location": "Busan"}
            room.meeting_settings = settings
            db.commit()
        with self.assertRaises(ac.StaleProposalError):
            self.approve(record)

    def test_apply_mismatch_rolls_back_everything(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        record = self.propose()
        original = ac._assert_matches
        ac._assert_matches = lambda *a, **k: (_ for _ in ()).throw(ac.ProposalApplyMismatchError("x"))
        self.addCleanup(setattr, ac, "_assert_matches", original)
        with self.assertRaises(ac.ProposalApplyMismatchError):
            self.approve(record)
        room = self.room()
        self.assertEqual((room.agent_input_revision, room.meeting_settings["coordination"]["durationMinutes"]), (5, 60))
        self.assertEqual(self._row(self.run_id).status, "ALL_AVAILABLE")
        self.assertEqual(self.proposal_row(record.id).status, "PROPOSED")

    def test_personal_availability_is_own_only_and_creates_a_new_version(self) -> None:
        slot = {"date": "2026-11-05", "start_minute": 600, "end_minute": 660, "time_zone": "Asia/Seoul"}
        intent = lambda who: {"kind": "SET_PERSONAL_AVAILABILITY", "participant_id": who,  # noqa: E731
                              "date": "2026-11-05", "slots": [slot]}
        self.use(FakeQwen([intent(MEMBER)]))
        with self.assertRaises(ac.InvalidProposalError) as raised:  # host edits someone else
            self.propose(actor=HOST, key="a")
        self.assertEqual(raised.exception.code, "AVAILABILITY_PERMISSION_DENIED")

        record = self.propose(actor=MEMBER, key="b", text="내 가능 시간을 10시로")
        with Session(self.engine) as db:
            member = db.scalar(select(RoomMember).where(RoomMember.account_id == MEMBER))
            before = db.scalar(select(ConditionSubmission.version).where(
                ConditionSubmission.room_member_id == member.id).order_by(ConditionSubmission.version.desc()))
        applied = self.approve(record, actor=MEMBER)
        self.assertEqual(applied.status, "APPLIED")
        with Session(self.engine) as db:
            after = db.scalar(select(ConditionSubmission.version).where(
                ConditionSubmission.room_member_id == member.id).order_by(ConditionSubmission.version.desc()))
        self.assertEqual(after, (before or 0) + 1)
        self.assertEqual(self.room().agent_input_revision, 6)

    def test_rejected_proposal_never_applies(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        record = self.propose()
        rejected = ac.reject_change_proposal(
            self.factory, room_id="room-1", proposal_id=record.id, actor_account_id=HOST)
        self.assertEqual(rejected.status, "REJECTED")
        self.assertFalse(ac.reject_change_proposal(
            self.factory, room_id="room-1", proposal_id=record.id, actor_account_id=HOST).changed)
        with self.assertRaises(ac.ProposalNotApprovableError):
            self.approve(record)
        self.assertEqual(self.room().agent_input_revision, 5)

    def test_stale_runs_are_not_rebuilt_by_graph_sync(self) -> None:
        self.use(FakeQwen([DURATION_90]))
        ad.select_candidate(self.factory, None, run_id=self.run_id, room_id="room-1",
                            actor_account_id=HOST, candidate_id=self.cid)  # unsynced
        self.approve(self.propose())
        self.assertFalse(ad._claim_sync(self.factory, self.run_id, "x"))


@unittest.skipUnless(
    os.getenv("POTATO_TEST_QWEN_URL"),
    "SKIP: set POTATO_TEST_QWEN_URL to the TEST Qwen endpoint (port 8081); never 8080",
)
class QwenLiveTests(ChangeBase):
    def test_live_qwen_produces_a_validated_proposal(self) -> None:
        ac.agent_factory = lambda snapshot: build_proposal_agent(
            snapshot, config=LlamaCppConfig(base_url=os.environ["POTATO_TEST_QWEN_URL"])
        )
        record = self.propose(text="모임 시간을 90분으로 늘려줘")
        self.assertIn(record.status, ("PROPOSED", "CLARIFICATION_REQUIRED"))
        self.assertEqual(self.room().agent_input_revision, 5)  # proposing alone never applies


if __name__ == "__main__":
    unittest.main()
