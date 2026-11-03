"""v1/v2 domain boundary and explicit Potato Meet coordination rounds."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ADMIN_ENABLED", "0")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db_v21.models.agent import AgentCandidate, AgentCandidateMember, AgentRun, CoordinationRound  # noqa: E402
from db_v21.models.room import Room  # noqa: E402
from services import agent_change as ac  # noqa: E402
from services import agent_decision as ad  # noqa: E402
from services import coordination_round as cr  # noqa: E402
from services.agent_run import RoomHostRequiredError, RoundAlreadyFinalizedError, start_agent_run  # noqa: E402
from services.meeting_domain import is_potato_meet  # noqa: E402
from services.agent_worker import claim_next_agent_run, execute_agent_run  # noqa: E402
from tests.test_agent_consistency import ConsistencyBase  # noqa: E402
from tests.test_agent_change import DURATION_45, FakeQwen  # noqa: E402

HOST, MEMBER, OTHER = "account-host", "account-member", "account-no-submission"


class RoundBase(ConsistencyBase):
    def open_round(self, key="round-1", expected=0, actor=HOST, reason=None):
        return cr.open_next_coordination_round(
            self.factory, room_id="room-1", actor_account_id=actor,
            idempotency_key=key, expected_round=expected, reason=reason,
        )

    def consent_rows(self, run_id):
        with Session(self.engine) as db:
            ids = list(db.scalars(select(AgentCandidate.id).where(AgentCandidate.run_id == run_id)))
            return sorted(
                (m.candidate_id, m.room_member_id, m.consent_round, m.consent_status)
                for m in db.scalars(
                    select(AgentCandidateMember).where(AgentCandidateMember.candidate_id.in_(ids))
                )
            )


class DomainIdentificationTests(RoundBase):
    def test_potato_meet_is_identified_by_the_coordination_block(self) -> None:
        self.assertTrue(is_potato_meet(self.room()))
        room = self.room()
        room.meeting_settings = {"title": "v1", "roles": ["a"]}  # a /v1-created room
        self.assertFalse(is_potato_meet(room))


class OpenRoundTests(RoundBase):
    def test_opening_a_round_preserves_history_and_settings_and_inherits_nothing(self) -> None:
        run2, _ = self.second_run()  # an undecided Run in the closing round
        self.finalize_run()
        before_room, before_run = self.room(), self._row(self.run_id)
        consents_before = self.consent_rows(self.run_id)

        opening = self.open_round(reason="일정 재조정")
        self.assertEqual(
            (opening.from_round, opening.to_round, opening.closed_run_id, opening.changed),
            (0, 1, self.run_id, True),
        )
        room = self.room()
        self.assertEqual(room.coordination_round, 1)
        self.assertEqual(room.meeting_settings, before_room.meeting_settings)  # coordination preserved
        self.assertEqual(room.agent_input_revision, before_room.agent_input_revision + 1)
        self.assertEqual(room.revision, before_room.revision + 1)
        self.assertEqual(room.current_round, before_room.current_round)  # /v1 role round untouched
        self.assertEqual(room.progress_status, before_room.progress_status)

        run = self._row(self.run_id)  # the finalized original is byte-for-byte history
        for column in ("status", "approval_status", "approval_by_member_id", "approval_at",
                       "selected_candidate_id", "finalized_at", "finalized_room_round",
                       "source_revision", "input_snapshot_hash", "decision_version"):
            self.assertEqual(getattr(run, column), getattr(before_run, column), column)
        self.assertEqual(self.consent_rows(self.run_id), consents_before)
        self.assertEqual(self._row(run2).status, "STALE")  # undecided work does not carry over
        self.assertFalse(self.final_result().finalized)
        self.assertEqual(self.final_result().coordination_round, 1)

    def test_new_round_run_starts_with_empty_consent_and_can_be_finalized_separately(self) -> None:
        self.finalize_run()
        self.open_round()
        revision = self.room().agent_input_revision
        with Session(self.engine) as db:
            new = start_agent_run(
                db, room_id="room-1", actor_account_id=HOST,
                idempotency_key="after-round", request={"expectedInputRevision": revision},
            )
        claim = claim_next_agent_run(self.factory, worker_id="w3", lease_seconds=30)
        result = execute_agent_run(claim, self.factory, lease_seconds=30, checkpointer=self.saver)
        cid = result.candidates[0].candidate.candidate_id
        self.assertTrue(all(row[3] is None for row in self.consent_rows(new.run_id)))  # no inherited consent
        self.finalize_run(new.run_id, cid)
        self.assertEqual(self._row(new.run_id).finalized_room_round, 1)
        self.assertEqual(self._row(self.run_id).finalized_room_round, 0)  # both finals coexist
        self.assertEqual(self.final_result().run_id, new.run_id)  # current round's result

    def test_old_run_and_pending_proposals_cannot_continue_in_the_new_round(self) -> None:
        self.use(FakeQwen([DURATION_45]))
        pending = self.propose()
        self.finalize_run()
        self.open_round()
        with self.assertRaises(ad.AlreadyFinalizedError):  # the final record stays immutable
            ad.record_consent(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                              actor_account_id=HOST, decision="DISAGREE")
        with self.assertRaises(ac.StaleProposalError):  # made against the old input revision
            self.approve(pending)
        self.assertEqual(self.proposal_row(pending.id).status, "SUPERSEDED")

    def test_replay_is_idempotent_and_conflicts_are_typed(self) -> None:
        self.finalize_run()
        first = self.open_round(key="k", reason="x")
        again = self.open_round(key="k", reason="x")
        self.assertEqual((again.changed, again.id, self.room().coordination_round), (False, first.id, 1))
        with self.assertRaises(cr.RoundKeyReusedError):
            self.open_round(key="k", reason="different")
        with self.assertRaises(cr.RoundConflictError):  # stale caller still thinks round 0
            self.open_round(key="k2", expected=0)
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(CoordinationRound)))), 1)

    def test_preconditions(self) -> None:
        with self.assertRaises(cr.RoundNotFinalizedError):  # nothing final yet
            self.open_round()
        self.finalize_run()
        with self.assertRaises(RoomHostRequiredError):
            self.open_round(actor=MEMBER)
        for bad in (dict(expected=-1), dict(key=" "), dict(reason="x" * 501)):
            with self.assertRaises(cr.InvalidRoundRequestError):
                self.open_round(**bad)
        self.set_room(progress_status="cancelled")
        with self.assertRaises(cr.RoomNotOpenError):
            self.open_round()
        self.set_room(progress_status="collecting", meeting_settings={"roles": ["a"]})
        with self.assertRaises(cr.NotPotatoMeetError):
            self.open_round(key="other")
        self.assertEqual(self.room().coordination_round, 0)


class StartRunGuardTests(RoundBase):
    def test_no_new_run_in_a_finalized_round_but_replay_still_returns_the_existing_run(self) -> None:
        with Session(self.engine) as db:
            first = start_agent_run(db, room_id="room-1", actor_account_id=HOST,
                                    idempotency_key="again", request={"expectedInputRevision": 5})
        self.finalize_run()
        with Session(self.engine) as db:
            with self.assertRaises(RoundAlreadyFinalizedError):
                start_agent_run(db, room_id="room-1", actor_account_id=HOST,
                                idempotency_key="new-key", request={"expectedInputRevision": 5})
        with Session(self.engine) as db:
            replay = start_agent_run(db, room_id="room-1", actor_account_id=HOST,
                                     idempotency_key="again", request={"expectedInputRevision": 5})
        self.assertEqual((replay.run_id, replay.replayed), (first.run_id, True))
        with Session(self.engine) as db:
            queued = list(db.scalars(select(AgentRun.id).where(AgentRun.status == "QUEUED")))
        self.assertEqual(queued, [first.run_id])  # no additional Run was created


class CrossDomainTests(RoundBase):
    def test_agent_cannot_finalize_a_room_the_role_assignment_already_finalized(self) -> None:
        ad.select_candidate(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                            actor_account_id=HOST, candidate_id=self.cid)
        for actor in (HOST, MEMBER, OTHER):
            ad.record_consent(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                              actor_account_id=actor, decision="AGREE")
        ad.decide_approval(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                           actor_account_id=HOST, decision="APPROVE")
        self.set_room(progress_status="finalized")  # /v1 finalize happened first
        with self.assertRaises(ad.RoleAssignmentFinalizedError):
            ad.finalize_meeting(self.factory, self.saver, run_id=self.run_id, room_id="room-1",
                                actor_account_id=HOST)
        self.assertIsNone(self._row(self.run_id).finalized_at)


if __name__ == "__main__":
    unittest.main()
