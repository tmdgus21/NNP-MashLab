"""Decision persistence tests: select -> consent -> approval -> finalize (SQLite)."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db_v21.models.agent import AgentCandidate, AgentCandidateMember, AgentRun
from db_v21.models.room import Room, RoomMember
from potato_agent.graph import checkpoint_serde
from services import agent_decision as ad
from services.agent_run import (
    RoomHostRequiredError,
    RoomMembershipRequiredError,
)
from tests.test_agent_resume import ResumeTestBase, sqlite_saver

HOST, MEMBER, OTHER = "account-host", "account-member", "account-no-submission"


class DecisionBase(ResumeTestBase):
    def setUp(self) -> None:
        super().setUp()
        cm = sqlite_saver(self.ckpt)
        self.saver = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.run_id, self.candidate = self._solve(checkpointer=self.saver)
        self.cid = self.candidate.candidate_id  # API-visible (DB) id

    def _call(self, fn, actor, saver="default", **kw):
        saver = self.saver if saver == "default" else saver
        return fn(
            self.factory, saver, run_id=self.run_id, room_id="room-1",
            actor_account_id=actor, **kw,
        )

    def select(self, actor=HOST, cid=None, **kw):
        return self._call(ad.select_candidate, actor, candidate_id=cid or self.cid, **kw)

    def consent(self, actor, decision="AGREE", **kw):
        return self._call(ad.record_consent, actor, decision=decision, **kw)

    def approve(self, actor=HOST, decision="APPROVE", **kw):
        return self._call(ad.decide_approval, actor, decision=decision, **kw)

    def finalize(self, actor=HOST, **kw):
        return self._call(ad.finalize_meeting, actor, **kw)

    def all_agree(self):
        for actor in (HOST, MEMBER, OTHER):
            result = self.consent(actor)
        return result

    def graph_values(self):
        row = self._row(self.run_id)
        tup = self.saver.get_tuple(
            {"configurable": {"thread_id": row.checkpoint_thread_id, "checkpoint_ns": ""}}
        )
        return tup.checkpoint["channel_values"]


class DecisionFlowTests(DecisionBase):
    def test_graph_candidate_id_is_persisted_and_unique(self) -> None:
        with Session(self.engine) as db:
            rows = list(db.scalars(select(AgentCandidate).where(AgentCandidate.run_id == self.run_id)))
        self.assertTrue(all(r.graph_candidate_id for r in rows))
        self.assertNotEqual(rows[0].id, rows[0].graph_candidate_id)

    def test_full_flow_persists_each_state_and_keeps_approval_separate(self) -> None:
        result = self.select()
        self.assertEqual(
            (result.state.selected_candidate_id, result.state.decision_version, result.state.consent_round),
            (self.cid, 1, 1),
        )
        self.assertEqual(result.state.graph_sync, "SYNCED")
        for actor in (HOST, MEMBER):
            result = self.consent(actor)
        self.assertFalse(result.state.all_agreed)
        self.assertEqual(result.state.status, "ALL_AVAILABLE")
        result = self.consent(OTHER)
        self.assertEqual(
            (result.state.status, result.state.approval_status, result.state.all_agreed),
            ("AWAITING_APPROVAL", "PENDING", True),
        )
        result = self.approve()
        self.assertEqual(result.state.approval_status, "APPROVED")
        self.assertFalse(result.state.finalized)  # approval != finalization
        result = self.finalize()
        self.assertTrue(result.state.finalized)
        row = self._row(self.run_id)
        self.assertIsNotNone(row.approval_by_member_id)
        self.assertIsNotNone(row.finalized_at)
        self.assertEqual(row.graph_synced_version, row.decision_version)
        self.assertEqual(self.graph_values()["approval_decision"], "APPROVED")
        self.assertFalse(self.graph_values().get("meeting_finalized"))  # AI never finalizes

    def test_only_host_selects_approves_and_finalizes(self) -> None:
        for call in (
            lambda: self.select(MEMBER),
            lambda: self.approve(MEMBER),
            lambda: self.finalize(MEMBER),
        ):
            with self.assertRaises(RoomHostRequiredError):
                call()
        with self.assertRaises(RoomMembershipRequiredError):
            self.consent("account-pending")

    def test_consent_requires_selection_and_actual_attendance(self) -> None:
        with self.assertRaises(ad.NoSelectionError):
            self.consent(MEMBER)
        self.select()
        with Session(self.engine) as db:  # OTHER is not an actual attendee of this candidate
            member = db.scalar(select(RoomMember).where(RoomMember.account_id == OTHER))
            db.get(AgentCandidateMember, (self.cid, member.id, 1)).participation_status = "UNAVAILABLE"
            db.commit()
        with self.assertRaises(ad.NotAnAttendeeError):
            self.consent(OTHER)
        self.consent(HOST)
        result = self.consent(MEMBER)
        # approval needs only the actual attendees; the absent member is not required
        self.assertEqual((result.state.all_agreed, result.state.approval_status), (True, "PENDING"))

    def test_non_response_is_never_treated_as_decline(self) -> None:
        self.select()
        result = self.consent(HOST)
        self.assertEqual(
            sorted(str(a.consent_status) for a in result.state.attendees),
            ["AGREE", "None", "None"],
        )
        with self.assertRaises(ad.ApprovalNotPendingError):
            self.approve()

    def test_disagree_and_withdraw_block_then_release_approval(self) -> None:
        self.select()
        self.all_agree()
        result = self.consent(MEMBER, "DISAGREE")
        self.assertEqual((result.state.status, result.state.approval_status), ("ALL_AVAILABLE", "NOT_REQUESTED"))
        result = self.consent(MEMBER, "WITHDRAW")
        self.assertIsNone(
            next(a for a in result.state.attendees if a.consent_status is None).consent_status
        )
        result = self.consent(MEMBER, "AGREE")
        self.assertEqual(result.state.approval_status, "PENDING")
        # graph rebuilt from the DB reflects the withdrawal/re-agree path
        self.assertEqual(
            sorted(self.graph_values()["consent_by_attendee_id"].values()), ["AGREE"] * 3
        )

    def test_replays_are_idempotent_and_do_not_bump_version(self) -> None:
        self.select()
        first = self.consent(HOST)
        again = self.consent(HOST)
        self.assertFalse(again.changed)
        self.assertEqual(first.state.decision_version, again.state.decision_version)
        self.all_agree()
        self.approve()
        replay = self.approve()
        self.assertFalse(replay.changed)
        with self.assertRaises(ad.ApprovalNotPendingError):
            self.approve(decision="REJECT")
        self.finalize()
        self.assertFalse(self.finalize().changed)

    def test_gates_for_approval_finalization_and_locked_consent(self) -> None:
        self.select()
        with self.assertRaises(ad.ApprovalRequiredError):
            self.finalize()
        self.all_agree()
        self.approve()
        with self.assertRaises(ad.ConsentLockedError):
            self.consent(MEMBER, "DISAGREE")
        self.finalize()
        with self.assertRaises(ad.AlreadyFinalizedError):
            self.select()

    def test_reselect_opens_new_round_and_invalidates_old_consent(self) -> None:
        self.select()
        self.all_agree()
        self.approve()
        result = self.select()  # same candidate, new round
        self.assertEqual(result.state.consent_round, 2)
        self.assertEqual(result.state.approval_status, "SUPERSEDED")
        self.assertTrue(all(a.consent_status is None for a in result.state.attendees))
        self.assertFalse(result.state.all_agreed)
        with Session(self.engine) as db:  # history of round 1 is retained
            old = list(db.scalars(select(AgentCandidateMember).where(
                AgentCandidateMember.candidate_id == self.cid,
                AgentCandidateMember.consent_round == 1)))
        self.assertTrue(all(m.consent_status == "AGREE" for m in old))
        self.assertEqual(self._row(self.run_id).approval_by_member_id, None)
        # the graph was rebuilt from the selection pause: old consents are gone
        self.assertNotIn("approval_decision", self.graph_values())
        self.assertEqual(self.graph_values().get("consent_by_attendee_id", {}), {})
        result = self.all_agree()
        self.assertEqual(result.state.approval_status, "PENDING")

    def test_unknown_or_unlinked_candidate_is_rejected(self) -> None:
        with self.assertRaises(ad.UnknownCandidateError):
            self.select(cid="nope")
        with Session(self.engine) as db:
            db.get(AgentCandidate, self.cid).graph_candidate_id = None
            db.commit()
        with self.assertRaises(ad.CandidateMismatchError):
            self.select()  # never matched by time/type

    def test_changed_meeting_marks_run_stale_before_any_change(self) -> None:
        self.select()
        with Session(self.engine) as db:
            db.get(Room, "room-1").agent_input_revision = 9
            db.commit()
        with self.assertRaises(ad.StaleDecisionError):
            self.consent(HOST)
        row = self._row(self.run_id)
        self.assertEqual(row.status, "STALE")
        with self.assertRaises(ad.RunNotDecidableError):
            self.consent(HOST)
        with Session(self.engine) as db:
            member = db.scalar(select(RoomMember).where(RoomMember.account_id == HOST))
            self.assertIsNone(db.get(AgentCandidateMember, (self.cid, member.id, 1)).consent_status)

    def test_cancelled_run_cannot_be_decided(self) -> None:
        with Session(self.engine) as db:
            db.get(AgentRun, self.run_id).cancel_requested_at = datetime.now(timezone.utc)
            db.commit()
        with self.assertRaises(ad.RunNotDecidableError):
            self.select()

    def test_expected_version_conflict_changes_nothing(self) -> None:
        self.select()
        with self.assertRaises(ad.VersionConflictError):
            self.consent(HOST, expected_version=0)
        self.assertEqual(self._row(self.run_id).decision_version, 1)
        self.consent(HOST, expected_version=1)


class GraphSyncRecoveryTests(DecisionBase):
    def test_failed_graph_sync_keeps_command_and_is_repaired_by_replay(self) -> None:
        from langgraph.checkpoint.sqlite import SqliteSaver

        class Failing(SqliteSaver):
            def put(self, *a, **k):
                raise RuntimeError("checkpoint store down")

        connection = sqlite3.connect(str(self.ckpt), check_same_thread=False)
        self.addCleanup(connection.close)
        failing = Failing(connection, serde=checkpoint_serde())
        result = self.select(saver=failing)
        self.assertEqual(result.state.graph_sync, "PENDING")
        row = self._row(self.run_id)
        self.assertEqual((row.decision_version, row.graph_synced_version), (1, 0))
        self.assertIsNone(row.sync_owner)  # lease released after the failure
        self.assertEqual(row.selected_candidate_id, self.cid)  # command not lost
        # any later call re-drives the rebuild; the committed command is not redone
        self.assertEqual(ad.sync_run_graph(self.factory, self.saver, run_id=self.run_id), "SYNCED")
        row = self._row(self.run_id)
        self.assertEqual((row.decision_version, row.graph_synced_version), (1, 1))
        self.assertEqual(self.graph_values()["selected_candidate_id"],
                         self.graph_candidate_id())

    def graph_candidate_id(self) -> str:
        with Session(self.engine) as db:
            return db.get(AgentCandidate, self.cid).graph_candidate_id

    def test_sync_is_noop_when_already_synced(self) -> None:
        self.select()
        ref = self._row(self.run_id).checkpoint_ref
        self.assertEqual(
            ad.sync_run_graph(self.factory, self.saver, run_id=self.run_id), "SYNCED"
        )
        self.assertEqual(self._row(self.run_id).checkpoint_ref, ref)

    def test_only_one_owner_can_hold_the_sync_lease(self) -> None:
        with Session(self.engine) as db:  # simulate committed but unsynced command
            db.get(AgentRun, self.run_id).decision_version = 1
            db.commit()
        self.assertTrue(ad._claim_sync(self.factory, self.run_id, "owner-a"))
        self.assertFalse(ad._claim_sync(self.factory, self.run_id, "owner-b"))
        # a loser must not release or advance the winner's lease
        self.assertFalse(ad._release_sync(self.factory, self.run_id, "owner-b", synced=1, ref="x"))
        self.assertEqual(self._row(self.run_id).sync_owner, "owner-a")
        with Session(self.engine) as db:  # crashed owner: lease expires
            db.get(AgentRun, self.run_id).sync_lease_expires_at = datetime.now(
                timezone.utc) - timedelta(seconds=1)
            db.commit()
        self.assertTrue(ad._claim_sync(self.factory, self.run_id, "owner-b"))
        self.assertFalse(ad._release_sync(self.factory, self.run_id, "owner-a", synced=1, ref="x"))
        self.assertTrue(ad._release_sync(self.factory, self.run_id, "owner-b", synced=1, ref="ok"))
        self.assertFalse(ad._claim_sync(self.factory, self.run_id, "owner-c"))  # synced now

    def test_run_without_durable_checkpoint_is_db_only(self) -> None:
        run_id, candidate = self._solve_memory()
        result = ad.select_candidate(
            self.factory, None, run_id=run_id, room_id="room-1",
            actor_account_id=HOST, candidate_id=candidate.candidate_id,
        )
        self.assertEqual(result.state.graph_sync, "NOT_APPLICABLE")

    def _solve_memory(self):
        # second Run in the same fixture is not possible; reuse the first Run
        # but drop its durable refs to emulate a memory-backend worker.
        with Session(self.engine) as db:
            row = db.get(AgentRun, self.run_id)
            row.base_checkpoint_ref = row.checkpoint_ref = None
            db.commit()
        return self.run_id, self.candidate


if __name__ == "__main__":
    unittest.main()
