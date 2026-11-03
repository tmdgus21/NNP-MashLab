"""Cross-service state consistency: final result, rounds, locks, checkpoint writers."""
from __future__ import annotations

import unittest

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db_v21.models.agent import AgentRun
from db_v21.models.room import Room, RoomMember
from services import agent_change as ac
from services import agent_decision as ad
from services import agent_resume as ar
from services.agent_run import start_agent_run
from services.agent_worker import claim_next_agent_run, execute_agent_run
from services.checkpoint_lease import claim_lease, release_lease
from tests import test_agent_change as tac

HOST, MEMBER, OTHER = tac.HOST, tac.MEMBER, tac.OTHER
DURATION_45, FakeQwen = tac.DURATION_45, tac.FakeQwen


class ConsistencyBase(tac.ChangeBase):
    def finalize_run(self, run_id=None, cid=None):
        run_id, cid = run_id or self.run_id, cid or self.cid

        def call(fn, actor, **kw):
            return fn(self.factory, self.saver, run_id=run_id, room_id="room-1",
                      actor_account_id=actor, **kw)

        call(ad.select_candidate, HOST, candidate_id=cid)
        for actor in (HOST, MEMBER, OTHER):
            call(ad.record_consent, actor, decision="AGREE")
        call(ad.decide_approval, HOST, decision="APPROVE")
        return call(ad.finalize_meeting, HOST)

    def final_result(self):
        return ad.get_final_result(self.factory, room_id="room-1", actor_account_id=MEMBER)

    def second_run(self):
        """A second Run in the same round, created through the existing start API."""
        with Session(self.engine) as db:
            run = start_agent_run(
                db, room_id="room-1", actor_account_id=HOST,
                idempotency_key="second", request={"expectedInputRevision": 5},
            )
        claim = claim_next_agent_run(self.factory, worker_id="w2", lease_seconds=30)
        result = execute_agent_run(claim, self.factory, lease_seconds=30, checkpointer=self.saver)
        return run.run_id, result.candidates[0].candidate.candidate_id

    def set_room(self, **values):
        with Session(self.engine) as db:
            for key, value in values.items():
                setattr(db.get(Room, "room-1"), key, value)
            db.commit()


class FinalResultContractTests(ConsistencyBase):
    def test_no_final_result_until_finalization(self) -> None:
        result = self.final_result()
        self.assertEqual((result.finalized, result.run_id, result.coordination_round), (False, None, 0))

    def test_final_result_is_the_agent_run_and_v1_room_states_are_untouched(self) -> None:
        before = self.room()
        self.finalize_run()
        result = self.final_result()
        self.assertTrue(result.finalized)
        self.assertEqual(
            (result.run_id, result.candidate_id, result.input_current, len(result.attendee_member_ids)),
            (self.run_id, self.cid, True, 3),
        )
        self.assertIsNotNone(result.approved_by_member_id)
        self.assertEqual(self._row(self.run_id).finalized_room_round, 0)
        after = self.room()  # rooms.* keep tracking only /v1 role-assignment finalization
        self.assertEqual(
            (after.progress_status, after.lifecycle_status, after.revision, after.agent_input_revision),
            (before.progress_status, before.lifecycle_status, before.revision, before.agent_input_revision),
        )

    def test_final_result_reports_when_input_moved_on_but_keeps_history(self) -> None:
        self.finalize_run()
        with Session(self.engine) as db:  # a /v1-style edit: hash changes, revision does not
            room = db.get(Room, "room-1")
            room.meeting_settings = {
                **room.meeting_settings,
                "coordination": {**room.meeting_settings["coordination"], "location": "Busan"},
            }
            db.commit()
        result = self.final_result()
        self.assertEqual((result.finalized, result.input_current), (True, False))

    def test_v1_role_plan_rounds_do_not_touch_the_agent_final_result(self) -> None:
        self.finalize_run()
        self.set_room(current_round=7)  # every /v1 calculation bumps this counter
        self.assertTrue(self.final_result().finalized)
        self.use(FakeQwen([DURATION_45]))
        with self.assertRaises(ac.RoundAlreadyFinalizedError):  # still immutable
            self.propose()

    def test_new_coordination_round_hides_the_old_final_result_without_changing_it(self) -> None:
        self.finalize_run()
        old = self._row(self.run_id)
        self.set_room(coordination_round=1)
        self.assertFalse(self.final_result().finalized)
        again = self._row(self.run_id)
        self.assertEqual((again.status, again.finalized_at, again.finalized_room_round),
                         (old.status, old.finalized_at, 0))

    def test_only_one_finalized_run_per_room_round(self) -> None:
        run2, cid2 = self.second_run()  # start_agent_run refuses once a round is final
        self.finalize_run()
        with self.assertRaises(ad.RoundAlreadyFinalizedError):
            self.finalize_run(run2, cid2)
        self.assertIsNone(self._row(run2).finalized_at)
        with self.assertRaises(IntegrityError):  # DB-level defence behind the service check
            with Session(self.engine) as db:
                db.execute(update(AgentRun).where(AgentRun.id == run2).values(
                    finalized_at=self._row(self.run_id).finalized_at, finalized_room_round=0))
                db.commit()
        # a different round may hold its own final result
        self.set_room(coordination_round=1)
        self.assertFalse(self.final_result().finalized)


class RoundPolicyTests(ConsistencyBase):
    def test_changes_are_blocked_after_finalization_and_nothing_is_touched(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        pending = self.propose(key="before")  # made before the meeting was finalized
        self.finalize_run()
        with self.assertRaises(ac.RoundAlreadyFinalizedError):
            self.propose(key="after")
        with self.assertRaises(ac.RoundAlreadyFinalizedError):
            self.approve(pending)
        self.assertEqual(self.proposal_row(pending.id).status, "PROPOSED")  # not applied, not lost
        self.assertEqual(self.room().agent_input_revision, 5)
        run = self._row(self.run_id)
        self.assertEqual((run.status, run.finalized_at is not None), ("AWAITING_APPROVAL", True))

    def test_explicit_new_round_allows_readjustment_as_a_new_run(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        self.finalize_run()
        self.set_room(coordination_round=1)  # what services.coordination_round does
        applied = self.approve(self.propose())
        self.assertEqual(applied.status, "APPLIED")
        old, new = self._row(self.run_id), self._row(applied.resulting_run_id)
        self.assertEqual((old.status, old.finalized_room_round), ("AWAITING_APPROVAL", 0))  # untouched
        self.assertEqual((new.status, new.finalized_at), ("QUEUED", None))
        self.assertFalse(self.final_result().finalized)

    def test_room_states_mirror_v1_immutability(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        self.set_room(progress_status="finalized")  # /v1 role-assignment finalized
        with self.assertRaises(ac.RoomNotMutableError):
            self.propose()
        self.set_room(progress_status="cancelled")
        with self.assertRaises(ac.RoomNotMutableError):
            self.propose(key="c")
        with self.assertRaises(ad.RoomNotActiveError):
            ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                                actor_account_id=HOST, candidate_id=self.cid)
        self.assertIsNone(self._row(self.run_id).selected_candidate_id)


class OrderingTests(ConsistencyBase):
    """Both orders of input change vs. finalization end in one consistent state."""

    def test_input_change_first_makes_finalization_impossible(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        record = self.propose()
        ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                            actor_account_id=HOST, candidate_id=self.cid)
        for actor in (HOST, MEMBER, OTHER):
            ad.record_consent(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                              actor_account_id=actor, decision="AGREE")
        ad.decide_approval(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                           actor_account_id=HOST, decision="APPROVE")
        self.approve(record)  # input change lands before the finalization
        with self.assertRaises(ad.RunNotDecidableError):
            ad.finalize_meeting(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                                actor_account_id=HOST)
        run = self._row(self.run_id)
        self.assertEqual((run.status, run.finalized_at), ("STALE", None))
        self.assertFalse(self.final_result().finalized)

    def test_finalization_first_makes_input_change_impossible(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        record = self.propose()
        self.finalize_run()
        with self.assertRaises(ac.RoundAlreadyFinalizedError):
            self.approve(record)
        self.assertTrue(self.final_result().finalized)
        self.assertEqual(self.room().agent_input_revision, 5)

    def test_consent_after_input_change_is_rejected_and_replays_stay_idempotent(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                            actor_account_id=HOST, candidate_id=self.cid)
        applied = self.approve(self.propose())
        with self.assertRaises(ad.RunNotDecidableError):
            ad.record_consent(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                              actor_account_id=HOST, decision="AGREE")
        again = self.approve(self.propose())  # same key: replay of the APPLIED proposal
        self.assertEqual((again.changed, again.resulting_run_id), (False, applied.resulting_run_id))

    def test_double_finalize_is_idempotent_and_keeps_one_result(self) -> None:
        self.finalize_run()
        again = ad.finalize_meeting(self.factory, self.saver, run_id=self.run_id,
                                    room_id="room-1", actor_account_id=HOST)
        self.assertFalse(again.changed)
        self.assertTrue(self.final_result().finalized)


class RevisionPathTests(ConsistencyBase):
    def test_decisions_never_touch_room_revisions(self) -> None:
        before = self.room()
        self.finalize_run()
        after = self.room()
        self.assertEqual((after.revision, after.agent_input_revision),
                         (before.revision, before.agent_input_revision))

    def test_approved_change_bumps_both_counters_exactly_once(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        before = self.room()
        record = self.propose()
        self.approve(record)
        self.approve(record)  # replay
        after = self.room()
        self.assertEqual((after.agent_input_revision, after.revision),
                         (before.agent_input_revision + 1, before.revision + 1))

    def test_v1_style_edit_changes_the_hash_not_the_revision_and_is_still_detected(self) -> None:
        with Session(self.engine) as db:
            room = db.get(Room, "room-1")
            room.meeting_settings = {
                **room.meeting_settings,
                "coordination": {**room.meeting_settings["coordination"], "location": "Busan"},
            }
            db.commit()
        self.assertEqual(self.room().agent_input_revision, 5)
        with self.assertRaises(ad.StaleDecisionError):
            ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                                actor_account_id=HOST, candidate_id=self.cid)
        self.assertEqual(self._row(self.run_id).status, "STALE")  # committed before the 409


class CheckpointWriterTests(ConsistencyBase):
    def resume_select(self):
        return ar.resume_agent_run(
            self.factory, self.saver, run_id=self.run_id, actor_account_id=HOST,
            kind="candidate_selection", payload={"candidateId": self.cid, "inputRevision": 5},
        )

    def test_low_level_resume_is_refused_once_the_decision_flow_owns_the_run(self) -> None:
        ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                            actor_account_id=HOST, candidate_id=self.cid)
        ref = self._row(self.run_id).checkpoint_ref
        with self.assertRaises(ar.ResumeManagedByDecisionError):
            self.resume_select()
        row = self._row(self.run_id)
        self.assertEqual((row.checkpoint_ref, row.sync_owner), (ref, None))  # lease released

    def test_resume_cannot_run_while_another_writer_holds_the_lease(self) -> None:
        self.assertTrue(claim_lease(self.factory, self.run_id, "decision-sync"))
        ref = self._row(self.run_id).checkpoint_ref
        with self.assertRaises(ar.ResumeConflictError):
            self.resume_select()
        self.assertEqual(self._row(self.run_id).checkpoint_ref, ref)
        self.assertEqual(self._row(self.run_id).sync_owner, "decision-sync")  # not stolen

    def test_decision_rebuild_waits_while_a_resume_holds_the_lease(self) -> None:
        self.assertTrue(claim_lease(self.factory, self.run_id, "resume"))
        ref = self._row(self.run_id).checkpoint_ref
        result = ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                                     actor_account_id=HOST, candidate_id=self.cid)
        self.assertEqual(result.state.graph_sync, "PENDING")  # command committed, rebuild deferred
        self.assertEqual(self._row(self.run_id).checkpoint_ref, ref)
        release_lease(self.factory, self.run_id, "resume")
        self.assertEqual(ad.sync_run_graph(self.factory, self.saver, run_id=self.run_id), "SYNCED")

    def test_unmanaged_resume_still_works_and_releases_the_lease(self) -> None:
        outcome = self.resume_select()
        self.assertEqual(outcome.next_pause_kind, "participant_consents")
        self.assertIsNone(self._row(self.run_id).sync_owner)
        # the decision flow then rebuilds from the DB and takes over
        result = ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                                     actor_account_id=HOST, candidate_id=self.cid)
        self.assertEqual(result.state.graph_sync, "SYNCED")

    def test_decision_committed_mid_resume_wins_and_resume_does_not_write_the_ref(self) -> None:
        real = ar.resume_pending

        def interleaved(*args, **kwargs):
            outcome = real(*args, **kwargs)
            # a host command commits while the resume still holds the lease
            ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                                actor_account_id=HOST, candidate_id=self.cid)
            return outcome

        ar.resume_pending = interleaved
        self.addCleanup(setattr, ar, "resume_pending", real)
        with self.assertRaises(ar.ResumeManagedByDecisionError):
            self.resume_select()
        row = self._row(self.run_id)
        self.assertEqual((row.decision_version, row.graph_synced_version, row.sync_owner), (1, 0, None))
        self.assertEqual(ad.sync_run_graph(self.factory, self.saver, run_id=self.run_id), "SYNCED")
        self.assertEqual(self._row(self.run_id).graph_synced_version, 1)


if __name__ == "__main__":
    unittest.main()
