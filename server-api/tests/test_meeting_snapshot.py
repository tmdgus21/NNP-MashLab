from __future__ import annotations

import unittest
import threading
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from db_v21 import Base
from db_v21.models.account import Account
from db_v21.models.admin import IdempotencyRecord
from db_v21.models.agent import (
    AgentCandidate,
    AgentCandidateMember,
    AgentRun,
    RoomInvitation,
)
from db_v21.models.condition import ConditionAvailableSlot, ConditionSubmission
from db_v21.models.room import Room, RoomMember
from services.meeting_snapshot import (
    AvailabilityStatus,
    EligibilityStatus,
    InvitationStatus,
    MeetingSnapshot,
    ResponseStatus,
    SnapshotConfigurationError,
    SnapshotDataError,
    UnsupportedCoordinationVersionError,
    _slot_minutes,
    _to_utc,
    build_meeting_snapshot,
)
from services.agent_run import (
    AccountNotAllowedError,
    AuthenticationRequiredError,
    IdempotencyConflictError,
    InputRevisionConflictError,
    MeetingNotFoundError,
    RoomHostRequiredError,
    RoomMembershipRequiredError,
    StartAgentRunRequest,
    UnsupportedUserRequestError,
    authorize_room_host,
    start_agent_run,
)
from services.agent_solver import (
    AgentCandidateValidationError,
    AgentSolverCancelledError,
    AgentSolverTimeoutError,
    AgentSolverUnknownError,
    StaleAgentRunError,
    run_agent_solver,
)
from services.agent_worker import (
    WorkerLeaseLostError,
    claim_next_agent_run,
    execute_agent_run,
    request_agent_run_cancel,
    retry_failed_agent_run,
)


class MeetingSnapshotBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self._insert_fixture()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def _coordination_settings() -> dict:
        return {
            "coordination": {
                "schemaVersion": 1,
                "activity": "Planning",
                "location": "Seoul",
                "durationMinutes": 60,
                "dates": ["2026-11-05", "2026-11-06"],
                "excludedDates": ["2026-11-06"],
                "timeZone": "Asia/Seoul",
                "minimumAttendeeCount": 2,
                "requiredStartMinutesByDate": {"2026-11-05": 540},
                "absoluteTimeWindows": [
                    {
                        "date": "2026-11-05",
                        "startMinute": 480,
                        "endMinute": 720,
                    }
                ],
            }
        }

    def _insert_fixture(self) -> None:
        accounts = {
            key: Account(
                id=f"account-{key}",
                login_email=f"{key}@example.test",
                password_hash="test-hash",
            )
            for key in ("host", "member", "no-submission", "pending", "declined", "excluded")
        }
        self.db.add_all(accounts.values())
        self.db.flush()

        self.room = Room(
            id="room-1",
            code="ROOM0001",
            created_by_account_id=accounts["host"].id,
            host_member_id="member-host",
            title="Planning",
            starts_at=datetime(2026, 11, 5, tzinfo=timezone.utc),
            ends_at=datetime(2026, 11, 7, tzinfo=timezone.utc),
            meeting_settings=self._coordination_settings(),
            revision=23,
            agent_input_revision=4,
        )
        host = RoomMember(
            id="member-host",
            room_id=self.room.id,
            account_id=accounts["host"].id,
            nickname="Host",
            room_role="OWNER",
        )
        member = RoomMember(
            id="member-attending",
            room_id=self.room.id,
            account_id=accounts["member"].id,
            nickname="Attendee",
        )
        no_submission = RoomMember(
            id="member-no-submission",
            room_id=self.room.id,
            account_id=accounts["no-submission"].id,
            nickname="No submission",
        )
        self.db.add_all([self.room, host, member, no_submission])
        self.db.flush()

        self.db.add_all(
            [
                RoomInvitation(
                    id="invite-member",
                    room_id=self.room.id,
                    account_id=accounts["member"].id,
                    invited_by_member_id=host.id,
                    invitation_status="SENT",
                    response_status="ACCEPTED",
                    eligibility_status="ACTIVE",
                    invited_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
                    responded_at=datetime(2026, 11, 1, 1, tzinfo=timezone.utc),
                ),
                RoomInvitation(
                    id="invite-pending",
                    room_id=self.room.id,
                    account_id=accounts["pending"].id,
                    invited_by_member_id=host.id,
                    invitation_status="SENT",
                    response_status="PENDING",
                    eligibility_status="ACTIVE",
                    invited_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
                ),
                RoomInvitation(
                    id="invite-declined",
                    room_id=self.room.id,
                    account_id=accounts["declined"].id,
                    invited_by_member_id=host.id,
                    invitation_status="SENT",
                    response_status="DECLINED",
                    eligibility_status="ACTIVE",
                    invited_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
                    responded_at=datetime(2026, 11, 1, 1, tzinfo=timezone.utc),
                ),
                RoomInvitation(
                    id="invite-excluded",
                    room_id=self.room.id,
                    account_id=accounts["excluded"].id,
                    invited_by_member_id=host.id,
                    invitation_status="SENT",
                    response_status="PENDING",
                    eligibility_status="EXCLUDED_BY_HOST",
                    invited_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
                    excluded_at=datetime(2026, 11, 2, tzinfo=timezone.utc),
                    excluded_by_member_id=host.id,
                    exclusion_reason="Host explicitly excluded",
                ),
            ]
        )
        old_submission = ConditionSubmission(
            id="submission-member-v1",
            room_member_id=member.id,
            version=1,
            confirmed={},
            submitted_at=datetime(2026, 11, 2, tzinfo=timezone.utc),
        )
        latest_submission = ConditionSubmission(
            id="submission-member-v2",
            room_member_id=member.id,
            version=2,
            confirmed={},
            submitted_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        )
        self.db.add_all([old_submission, latest_submission])
        self.db.flush()
        self.db.add_all(
            [
                ConditionAvailableSlot(
                    id="old-slot",
                    condition_submission_id=old_submission.id,
                    starts_at=datetime(2026, 11, 5, 7, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 11, 5, 8, tzinfo=timezone.utc),
                ),
                ConditionAvailableSlot(
                    id="slot-1",
                    condition_submission_id=latest_submission.id,
                    starts_at=datetime(2026, 11, 5, 9, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 11, 5, 9, 20, tzinfo=timezone.utc),
                ),
                ConditionAvailableSlot(
                    id="slot-2",
                    condition_submission_id=latest_submission.id,
                    starts_at=datetime(2026, 11, 5, 9, 15, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 11, 5, 9, 50, tzinfo=timezone.utc),
                ),
                ConditionAvailableSlot(
                    id="slot-3",
                    condition_submission_id=latest_submission.id,
                    starts_at=datetime(2026, 11, 5, 9, 50, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 11, 5, 10, tzinfo=timezone.utc),
                ),
            ]
        )
        self.db.commit()

    def _build(self, *, run_id: str = "run-1", consent_round: int = 1) -> MeetingSnapshot:
        return build_meeting_snapshot(
            self.db,
            room_id=self.room.id,
            agent_session_id="agent-session",
            run_id=run_id,
            consent_round=consent_round,
        )

    def _start_run(
        self,
        *,
        actor_account_id: str | None = "account-member",
        key: str = "request-key",
        expected_revision: int = 4,
        user_request: str | None = None,
        room_id: str = "room-1",
    ):
        with Session(self.engine) as db:
            return start_agent_run(
                db,
                room_id=room_id,
                actor_account_id=actor_account_id,
                idempotency_key=key,
                request={
                    "expectedInputRevision": expected_revision,
                    "userRequest": user_request,
                },
            )

    def test_builds_agent_snapshot_with_latest_submission_and_distinct_rsvp_states(self):
        snapshot = self._build()

        self.assertIsInstance(snapshot, MeetingSnapshot)
        self.assertEqual(snapshot.input_revision, 4)
        self.assertEqual(self.room.revision, 23)
        self.assertEqual(snapshot.minimum_attendee_count, 2)
        self.assertEqual(snapshot.dates, (date(2026, 11, 5), date(2026, 11, 6)))
        self.assertEqual(snapshot.excluded_dates, (date(2026, 11, 6),))
        self.assertEqual(
            snapshot.required_start_minutes_by_date,
            {date(2026, 11, 5): 540},
        )
        self.assertEqual(len(snapshot.absolute_time_windows), 1)

        participant_by_id = {
            participant.participant_id: participant
            for participant in snapshot.participants
        }
        self.assertEqual(
            participant_by_id["account-host"].role.value, "ORGANIZER"
        )
        self.assertEqual(
            participant_by_id["account-pending"].response_status,
            ResponseStatus.PENDING,
        )
        self.assertEqual(
            participant_by_id["account-declined"].response_status,
            ResponseStatus.DECLINED,
        )
        self.assertEqual(
            participant_by_id["account-excluded"].eligibility_status,
            EligibilityStatus.EXCLUDED_BY_HOST,
        )
        self.assertEqual(
            participant_by_id["account-excluded"].response_status,
            ResponseStatus.PENDING,
        )
        self.assertEqual(
            participant_by_id["account-excluded"].invitation_status,
            InvitationStatus.SENT,
        )

        availability = snapshot.availability_by_participant_id
        self.assertEqual(
            availability["account-member"].status,
            AvailabilityStatus.SUBMITTED,
        )
        self.assertEqual(availability["account-member"].submission_version, 2)
        self.assertEqual(
            [
                (slot.date, slot.start_minute, slot.end_minute, slot.time_zone)
                for slot in availability["account-member"].slots
            ],
            [(date(2026, 11, 5), 540, 600, "Asia/Seoul")],
        )
        self.assertEqual(
            availability["account-no-submission"].status,
            AvailabilityStatus.NOT_SUBMITTED,
        )
        self.assertEqual(availability["account-no-submission"].slots, ())
        self.assertEqual(
            availability["account-pending"].status,
            AvailabilityStatus.NOT_SUBMITTED,
        )
        self.assertEqual(self.room.agent_input_revision, 4)

    def test_hash_is_canonical_and_independent_of_run_context(self):
        first = self._build(run_id="run-1", consent_round=1)
        second = self._build(run_id="run-2", consent_round=8)
        self.assertEqual(first.input_snapshot_hash, second.input_snapshot_hash)
        self.assertEqual(len(first.input_snapshot_hash), 64)
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertNotEqual(first.consent_round, second.consent_round)
        self.room.revision += 1
        self.db.commit()
        self.assertEqual(first.input_snapshot_hash, self._build().input_snapshot_hash)
        self.room.agent_input_revision += 1
        self.db.commit()
        changed_input = self._build(run_id="run-3")
        self.assertNotEqual(first.input_snapshot_hash, changed_input.input_snapshot_hash)
        self.assertEqual(changed_input.input_revision, 5)

    def test_snapshot_is_usable_after_database_session_closes(self):
        snapshot = self._build()
        self.db.close()
        self.assertEqual(snapshot.title, "Planning")
        self.assertIn("account-member", snapshot.availability_by_participant_id)
        with self.assertRaises(ValidationError):
            snapshot.title = "mutated"

    def test_missing_and_unsupported_coordination_versions_are_typed(self):
        self.room.meeting_settings = {}
        self.db.commit()
        with self.assertRaises(SnapshotConfigurationError):
            self._build()

        self.room.meeting_settings = {
            "coordination": {"schemaVersion": 2}
        }
        self.db.commit()
        with self.assertRaises(UnsupportedCoordinationVersionError):
            self._build()

    def test_invalid_coordination_and_unrepresentable_availability_are_typed(self):
        settings = self._coordination_settings()
        settings["coordination"]["durationMinutes"] = 0
        self.room.meeting_settings = settings
        self.db.commit()
        with self.assertRaises(SnapshotConfigurationError):
            self._build()

        settings = self._coordination_settings()
        settings["coordination"]["absoluteTimeWindows"][0]["endMinute"] = 400
        self.room.meeting_settings = settings
        self.db.commit()
        with self.assertRaises(SnapshotConfigurationError):
            self._build()

        self.room.meeting_settings = self._coordination_settings()
        submission = self.db.get(ConditionSubmission, "submission-member-v2")
        assert submission is not None
        self.db.add(
            ConditionAvailableSlot(
                id="subminute-slot",
                condition_submission_id=submission.id,
                starts_at=datetime(2026, 11, 5, 11, 0, 1),
                ends_at=datetime(2026, 11, 5, 12, 0),
            )
        )
        self.db.commit()
        with self.assertRaises(SnapshotDataError):
            self._build()

    def test_accepted_invitation_without_active_membership_is_typed_data_error(self):
        invitation = self.db.get(RoomInvitation, "invite-pending")
        assert invitation is not None
        invitation.response_status = "ACCEPTED"
        invitation.responded_at = datetime(2026, 11, 3, tzinfo=timezone.utc)
        self.db.commit()
        with self.assertRaises(SnapshotDataError):
            self._build()

    def test_slot_normalization_handles_utc_and_midnight(self):
        naive_utc = _to_utc(datetime(2026, 11, 5, 0, 0))
        self.assertEqual(naive_utc, datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc))
        utc_slot = _slot_minutes(
            datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 5, 1, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(utc_slot, (date(2026, 11, 5), 540, 600))
        midnight_slot = _slot_minutes(
            datetime(2026, 11, 5, 23, tzinfo=timezone(timedelta(hours=9))),
            datetime(2026, 11, 6, 0, tzinfo=timezone(timedelta(hours=9))),
        )
        self.assertEqual(midnight_slot, (date(2026, 11, 5), 1380, 1440))
        with self.assertRaises(SnapshotDataError):
            _slot_minutes(
                datetime(2026, 11, 5, 23, tzinfo=timezone(timedelta(hours=9))),
                datetime(2026, 11, 6, 1, tzinfo=timezone(timedelta(hours=9))),
            )

    def test_run_is_queued_persisted_and_idempotently_replayed(self):
        created = self._start_run(key="same-key")
        self.assertFalse(created.replayed)
        self.assertEqual(created.status, "QUEUED")
        self.assertEqual(created.source_revision, 4)
        self.assertEqual(created.created_by_account_id, "account-member")
        self.assertEqual(created.created_by_member_id, "member-attending")
        self.assertEqual(created.snapshot.run_id, created.run_id)
        self.assertEqual(
            created.input_snapshot_hash,
            created.snapshot.input_snapshot_hash,
        )
        self.assertEqual(
            created.snapshot.availability_by_participant_id[
                "account-no-submission"
            ].status,
            AvailabilityStatus.NOT_SUBMITTED,
        )

        with Session(self.engine) as db:
            stored = db.get(AgentRun, created.run_id)
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertEqual(stored.status, "QUEUED")
            self.assertEqual(stored.created_by_member_id, "member-attending")
            self.assertEqual(stored.input_snapshot_hash, created.input_snapshot_hash)
            self.assertEqual(stored.input_snapshot["input_revision"], 4)
            ledger = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.resource_id == created.run_id
                )
            )
            self.assertIsNotNone(ledger)
            assert ledger is not None
            self.assertEqual(ledger.resource_type, "agent_run")
            self.assertNotEqual(ledger.key_hash, "same-key")

        replay = self._start_run(key="same-key")
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.run_id, created.run_id)
        self.assertEqual(replay.agent_session_id, created.agent_session_id)
        self.assertEqual(replay.input_snapshot_hash, created.input_snapshot_hash)
        with Session(self.engine) as db, db.begin():
            run = db.get(AgentRun, created.run_id)
            assert run is not None
            run.status = "ANALYZING"
        replay_after_worker_claim = self._start_run(key="same-key")
        self.assertTrue(replay_after_worker_claim.replayed)
        self.assertEqual(replay_after_worker_claim.status, "ANALYZING")

    def test_idempotency_key_reuse_with_different_request_conflicts(self):
        created = self._start_run(key="reuse-key")
        with self.assertRaises(IdempotencyConflictError):
            self._start_run(key="reuse-key", expected_revision=5)
        with Session(self.engine) as db:
            self.assertEqual(
                db.scalar(select(AgentRun.id).where(AgentRun.id == created.run_id)),
                created.run_id,
            )
            self.assertEqual(db.scalar(select(func.count()).select_from(AgentRun)), 1)

    def test_run_requires_active_authenticated_room_member(self):
        with self.assertRaises(RoomMembershipRequiredError):
            self._start_run(actor_account_id="account-pending")
        with self.assertRaises(AccountNotAllowedError):
            self._start_run(actor_account_id="account-not-present")
        with self.assertRaises(AuthenticationRequiredError):
            self._start_run(actor_account_id=None)
        with Session(self.engine) as db:
            with self.assertRaises(RoomHostRequiredError):
                authorize_room_host(
                    db,
                    room_id="room-1",
                    actor_account_id="account-member",
                )
            host = authorize_room_host(
                db,
                room_id="room-1",
                actor_account_id="account-host",
            )
            self.assertTrue(host.is_host)
        with self.assertRaises(MeetingNotFoundError):
            self._start_run(key="missing-room", room_id="missing-room")

    def test_stale_revision_and_unsupported_user_request_leave_no_records(self):
        with self.assertRaises(InputRevisionConflictError) as raised:
            self._start_run(key="stale-key", expected_revision=23)
        self.assertEqual(raised.exception.current_revision, 4)
        with Session(self.engine) as db, db.begin():
            room = db.get(Room, "room-1")
            assert room is not None
            room.agent_input_revision = 5
        with self.assertRaises(InputRevisionConflictError) as raised:
            self._start_run(key="changed-input-key", expected_revision=4)
        self.assertEqual(raised.exception.current_revision, 5)
        with self.assertRaises(UnsupportedUserRequestError):
            self._start_run(key="user-request-key", user_request="reschedule")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AgentRun)), 0)
            self.assertEqual(
                db.scalar(select(func.count()).select_from(IdempotencyRecord)), 0
            )

    def test_outer_transaction_rollback_removes_run_and_idempotency_record(self):
        with Session(self.engine) as db:
            with self.assertRaisesRegex(RuntimeError, "rollback request"):
                with db.begin():
                    result = start_agent_run(
                        db,
                        room_id="room-1",
                        actor_account_id="account-member",
                        idempotency_key="outer-rollback",
                        request={"expectedInputRevision": 4},
                    )
                    self.assertEqual(result.status, "QUEUED")
                    raise RuntimeError("rollback request")
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AgentRun)), 0)
            self.assertEqual(
                db.scalar(select(func.count()).select_from(IdempotencyRecord)), 0
            )

    def test_run_snapshot_hash_and_revision_are_immutable(self):
        result = self._start_run(key="immutable-key")
        with Session(self.engine) as db:
            run = db.get(AgentRun, result.run_id)
            self.assertIsNotNone(run)
            assert run is not None
            self.assertEqual(run.input_snapshot_hash, result.input_snapshot_hash)
            self.assertEqual(run.source_revision, result.source_revision)
            self.assertEqual(
                run.input_snapshot["input_snapshot_hash"],
                result.snapshot.input_snapshot_hash,
            )
        with self.assertRaises(ValidationError):
            result.snapshot.input_revision = 99

    def _create_solver_run(self, *, no_submission_start_minute: int):
        for member_id, start_minute in (
            ("member-host", 540),
            ("member-no-submission", no_submission_start_minute),
        ):
            submission = ConditionSubmission(
                id=f"solver-submission-{member_id}",
                room_member_id=member_id,
                version=1,
                confirmed={},
                submitted_at=datetime(2026, 11, 4, tzinfo=timezone.utc),
            )
            self.db.add(submission)
            self.db.flush()
            starts_at = datetime(2026, 11, 5) + timedelta(minutes=start_minute)
            self.db.add(
                ConditionAvailableSlot(
                    id=f"solver-slot-{member_id}",
                    condition_submission_id=submission.id,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=60),
                )
            )
        pending_invitation = self.db.get(RoomInvitation, "invite-pending")
        assert pending_invitation is not None
        pending_invitation.eligibility_status = "EXCLUDED_BY_HOST"
        pending_invitation.excluded_at = datetime(
            2026, 11, 4, tzinfo=timezone.utc
        )
        pending_invitation.excluded_by_member_id = "member-host"
        pending_invitation.exclusion_reason = "Excluded for solver fixture"
        self.room.agent_input_revision = 5
        self.db.commit()

        with Session(self.engine) as db:
            run = start_agent_run(
                db,
                room_id="room-1",
                actor_account_id="account-host",
                idempotency_key=f"solver-{no_submission_start_minute}",
                request={"expectedInputRevision": 5},
            )
        self.db.close()
        return run

    def test_solver_adapter_uses_detached_run_and_returns_validated_all_candidate(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        active_sessions = [0]
        base_session_type = Session
        self_test = self

        class TrackingSession(base_session_type):
            def __enter__(self):
                active_sessions[0] += 1
                return super().__enter__()

            def __exit__(self, *args):
                try:
                    return super().__exit__(*args)
                finally:
                    active_sessions[0] -= 1

        def session_factory():
            return TrackingSession(bind=self.engine)

        from potato_agent.ortools_adapter import CpSatSolverAdapter

        class SessionCheckingSolver:
            def __init__(self, *args, **kwargs):
                self.solver = CpSatSolverAdapter(*args, **kwargs)

            def solve_all_attendees(self, snapshot):
                self_test.assertEqual(active_sessions[0], 0)
                return self.solver.solve_all_attendees(snapshot)

            def solve_partial_attendees(self, snapshot, minimum_attendee_count):
                self_test.assertEqual(active_sessions[0], 0)
                return self.solver.solve_partial_attendees(
                    snapshot, minimum_attendee_count
                )

        with patch("services.agent_solver.CpSatSolverAdapter", SessionCheckingSolver):
            result = run_agent_solver(run, session_factory=session_factory)

        self.assertEqual(active_sessions[0], 0)
        self.assertEqual(result.status.value, "ALL_AVAILABLE")
        self.assertEqual(len(result.candidates), 1)
        self.assertTrue(result.candidates[0].verified)
        self.assertEqual(
            result.candidates[0].source_snapshot_hash,
            run.input_snapshot_hash,
        )

    def test_solver_adapter_runs_partial_only_after_proven_infeasibility(self):
        run = self._create_solver_run(no_submission_start_minute=720)
        result = run_agent_solver(
            run,
            session_factory=lambda: Session(self.engine),
        )

        self.assertEqual(result.status.value, "PARTIAL_ALTERNATIVE")
        self.assertEqual(result.all_solver_status.value, "INFEASIBLE")
        self.assertEqual(result.partial_solver_status.value, "OPTIMAL")
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(
            set(result.candidates[0].attendee_ids),
            {"account-host", "account-member"},
        )

    def test_solver_adapter_rejects_stale_run_before_returning_candidates(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        with Session(self.engine) as db:
            room = db.get(Room, "room-1")
            assert room is not None
            room.agent_input_revision += 1
            db.commit()

        with self.assertRaises(StaleAgentRunError):
            run_agent_solver(run, session_factory=lambda: Session(self.engine))

    def test_solver_adapter_rejects_hash_change_without_revision_increment(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        with Session(self.engine) as db:
            room = db.get(Room, "room-1")
            assert room is not None
            settings = dict(room.meeting_settings)
            settings["coordination"] = dict(settings["coordination"])
            settings["coordination"]["location"] = "Changed location"
            room.meeting_settings = settings
            db.commit()

        with self.assertRaises(StaleAgentRunError):
            run_agent_solver(run, session_factory=lambda: Session(self.engine))

    def test_solver_adapter_rechecks_snapshot_hash_after_solver_returns(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        from potato_agent.models import SolverResult, SolverStatus

        class MutatingSolver:
            def __init__(self, *args, **kwargs):
                pass

            def solve_all_attendees(self, snapshot):
                with Session(self_test.engine) as db:
                    room = db.get(Room, "room-1")
                    assert room is not None
                    settings = dict(room.meeting_settings)
                    settings["coordination"] = dict(settings["coordination"])
                    settings["coordination"]["location"] = "Changed during solve"
                    room.meeting_settings = settings
                    db.commit()
                return SolverResult(status=SolverStatus.INFEASIBLE)

            def solve_partial_attendees(self, snapshot, minimum_attendee_count):
                raise AssertionError("stale all-attendee solve must not run partial")

        self_test = self
        with patch("services.agent_solver.CpSatSolverAdapter", MutatingSolver):
            with self.assertRaises(StaleAgentRunError):
                run_agent_solver(run, session_factory=lambda: Session(self.engine))

    def test_solver_adapter_returns_typed_unknown_and_cancelled_errors(self):
        run = self._create_solver_run(no_submission_start_minute=540)

        from potato_agent.models import (
            RawCandidate,
            RecommendationType,
            SolverResult,
            SolverStatus,
        )

        class TimeoutSolver:
            def __init__(self, *args, **kwargs):
                pass

            def solve_all_attendees(self, snapshot):
                return SolverResult(status=SolverStatus.TIMEOUT)

            def solve_partial_attendees(self, snapshot, minimum_attendee_count):
                raise AssertionError("TIMEOUT must not trigger partial search")

        class UnknownSolver:
            def __init__(self, *args, **kwargs):
                pass

            def solve_all_attendees(self, snapshot):
                return SolverResult(status=SolverStatus.UNKNOWN)

            def solve_partial_attendees(self, snapshot, minimum_attendee_count):
                raise AssertionError("UNKNOWN must not trigger partial search")

        class InvalidCandidateSolver:
            def __init__(self, *args, **kwargs):
                pass

            def solve_all_attendees(self, snapshot):
                return SolverResult(
                    status=SolverStatus.FEASIBLE,
                    candidates=(
                        RawCandidate(
                            meeting_id=snapshot.meeting_id,
                            agent_run_id=snapshot.run_id,
                            source_revision=snapshot.input_revision,
                            source_snapshot_hash="incorrect-hash",
                            date=date(2026, 11, 5),
                            start_minute=540,
                            end_minute=600,
                            time_zone="Asia/Seoul",
                            recommendation_type=RecommendationType.ALL_AVAILABLE,
                            attendee_ids=(
                                "account-host",
                                "account-member",
                                "account-no-submission",
                            ),
                            unavailable_ids=(),
                        ),
                    ),
                )

            def solve_partial_attendees(self, snapshot, minimum_attendee_count):
                raise AssertionError("invalid all-attendee candidate cannot fall back")

        with patch("services.agent_solver.CpSatSolverAdapter", TimeoutSolver):
            with self.assertRaises(AgentSolverTimeoutError):
                run_agent_solver(run, session_factory=lambda: Session(self.engine))

        with patch("services.agent_solver.CpSatSolverAdapter", UnknownSolver):
            with self.assertRaises(AgentSolverUnknownError):
                run_agent_solver(run, session_factory=lambda: Session(self.engine))

        with patch(
            "services.agent_solver.CpSatSolverAdapter", InvalidCandidateSolver
        ):
            with self.assertRaises(AgentCandidateValidationError):
                run_agent_solver(run, session_factory=lambda: Session(self.engine))

        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(AgentSolverCancelledError):
            run_agent_solver(
                run,
                session_factory=lambda: Session(self.engine),
                cancellation_event=cancelled,
            )

    def test_worker_claims_runs_persists_top_three_and_member_partition_atomically(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(
            lambda: Session(self.engine),
            worker_id="worker-1",
            lease_seconds=30,
        )
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.run.run_id, run.run_id)
        self.assertEqual(claim.run.status, "RUNNING")
        self.assertIsNone(
            claim_next_agent_run(
                lambda: Session(self.engine),
                worker_id="worker-duplicate",
                lease_seconds=30,
            )
        )

        with Session(self.engine) as db:
            claimed = db.get(AgentRun, run.run_id)
            assert claimed is not None
            self.assertEqual(claimed.status, "RUNNING")
            self.assertEqual(claimed.worker_id, "worker-1")
            self.assertNotEqual(claimed.lease_token_hash, claim.lease_token)
            self.assertIsNotNone(claimed.lease_expires_at)

        result = execute_agent_run(
            claim,
            lambda: Session(self.engine),
            lease_seconds=30,
        )
        self.assertEqual(result.status, "ALL_AVAILABLE")
        self.assertEqual(len(result.candidates), 1)

        with Session(self.engine) as db:
            stored_run = db.get(AgentRun, run.run_id)
            assert stored_run is not None
            self.assertEqual(stored_run.status, "ALL_AVAILABLE")
            self.assertIsNone(stored_run.worker_id)
            self.assertIsNone(stored_run.lease_token_hash)
            self.assertIsNotNone(stored_run.completed_at)
            candidate_rows = list(
                db.scalars(
                    select(AgentCandidate)
                    .where(AgentCandidate.run_id == run.run_id)
                    .order_by(AgentCandidate.rank)
                )
            )
            self.assertEqual([item.rank for item in candidate_rows], [1])
            self.assertEqual(candidate_rows[0].candidate_type, "ALL_AVAILABLE")
            self.assertTrue(candidate_rows[0].verified)
            self.assertEqual(candidate_rows[0].meeting_date, date(2026, 11, 5))
            self.assertEqual(candidate_rows[0].starts_at.hour, 9)
            self.assertEqual(candidate_rows[0].starts_at.minute, 0)
            self.assertEqual(candidate_rows[0].ends_at.hour, 10)
            self.assertEqual(candidate_rows[0].source_revision, run.source_revision)
            self.assertEqual(
                candidate_rows[0].source_snapshot_hash,
                run.input_snapshot_hash,
            )
            members = list(
                db.scalars(
                    select(AgentCandidateMember).where(
                        AgentCandidateMember.candidate_id == candidate_rows[0].id
                    )
                )
            )
            self.assertEqual(len(members), 3)
            self.assertTrue(
                all(item.participation_status == "ATTENDING" for item in members)
            )
            self.assertTrue(all(item.consent_status is None for item in members))
            self.assertTrue(all(item.consent_round == run.snapshot.consent_round for item in members))
            self.assertEqual(
                {item.candidate.candidate_id for item in result.candidates},
                {candidate_rows[0].id},
            )

    def test_worker_persists_top_three_in_agent_order(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        with Session(self.engine) as db:
            initial_run = db.get(AgentRun, run.run_id)
            assert initial_run is not None
            initial_run.status = "CANCELLED"
            initial_run.completed_at = datetime.now(timezone.utc)
            room = db.get(Room, "room-1")
            assert room is not None
            settings = dict(room.meeting_settings)
            settings["coordination"] = dict(settings["coordination"])
            settings["coordination"].pop("requiredStartMinutesByDate")
            settings["coordination"]["absoluteTimeWindows"] = [
                {"date": "2026-11-05", "startMinute": 480, "endMinute": 720}
            ]
            room.meeting_settings = settings
            room.agent_input_revision += 1
            for member_id in (
                "member-host",
                "member-attending",
                "member-no-submission",
            ):
                latest = db.scalar(
                    select(ConditionSubmission)
                    .where(ConditionSubmission.room_member_id == member_id)
                    .order_by(ConditionSubmission.version.desc())
                    .limit(1)
                )
                assert latest is not None
                slots = list(
                    db.scalars(
                        select(ConditionAvailableSlot).where(
                            ConditionAvailableSlot.condition_submission_id
                            == latest.id
                        )
                    )
                )
                for slot in slots:
                    slot.starts_at = datetime(2026, 11, 5, 8)
                    slot.ends_at = datetime(2026, 11, 5, 12)
            db.commit()
            refreshed = start_agent_run(
                db,
                room_id="room-1",
                actor_account_id="account-host",
                idempotency_key="top-three-worker",
                request={"expectedInputRevision": 6},
            )

        claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-top-three"
        )
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.run.run_id, refreshed.run_id)
        result = execute_agent_run(claim, lambda: Session(self.engine))
        self.assertEqual(result.status, "ALL_AVAILABLE")
        self.assertEqual(len(result.candidates), 3)
        self.assertEqual([item.rank for item in result.candidates], [1, 2, 3])
        self.assertEqual(
            [item.candidate.start_minute for item in result.candidates],
            sorted(item.candidate.start_minute for item in result.candidates),
        )

    def test_worker_discards_result_if_cancel_requested_during_execution(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-cancel"
        )
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertTrue(
            request_agent_run_cancel(
                lambda: Session(self.engine), run_id=run.run_id
            )
        )

        result = execute_agent_run(claim, lambda: Session(self.engine))
        self.assertEqual(result.status, "CANCELLED")
        with Session(self.engine) as db:
            self.assertEqual(
                db.scalar(
                    select(func.count()).select_from(AgentCandidate).where(
                        AgentCandidate.run_id == run.run_id
                    )
                ),
                0,
            )

    def test_worker_cancels_queued_run_before_claim(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        self.assertTrue(
            request_agent_run_cancel(
                lambda: Session(self.engine), run_id=run.run_id
            )
        )
        self.assertIsNone(
            claim_next_agent_run(
                lambda: Session(self.engine), worker_id="worker-after-cancel"
            )
        )
        with Session(self.engine) as db:
            stored = db.get(AgentRun, run.run_id)
            assert stored is not None
            self.assertEqual(stored.status, "CANCELLED")
            self.assertIsNotNone(stored.cancel_requested_at)
            self.assertIsNotNone(stored.completed_at)

    def test_worker_persists_partial_candidate_attending_and_unavailable_members(self):
        run = self._create_solver_run(no_submission_start_minute=720)
        claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-partial"
        )
        self.assertIsNotNone(claim)
        assert claim is not None
        result = execute_agent_run(claim, lambda: Session(self.engine))
        self.assertEqual(result.status, "PARTIAL_ALTERNATIVE")
        with Session(self.engine) as db:
            candidate = db.scalar(
                select(AgentCandidate).where(AgentCandidate.run_id == run.run_id)
            )
            assert candidate is not None
            members = list(
                db.scalars(
                    select(AgentCandidateMember).where(
                        AgentCandidateMember.candidate_id == candidate.id
                    )
                )
            )
            status_by_member = {
                item.room_member_id: item.participation_status for item in members
            }
            self.assertEqual(status_by_member["member-host"], "ATTENDING")
            self.assertEqual(status_by_member["member-attending"], "ATTENDING")
            self.assertEqual(status_by_member["member-no-submission"], "UNAVAILABLE")
            self.assertTrue(all(item.consent_status is None for item in members))

    def test_worker_discards_solver_result_when_revision_changes_before_commit(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-stale"
        )
        self.assertIsNotNone(claim)
        assert claim is not None
        from services import agent_worker

        solve = agent_worker.run_agent_solver

        def mutate_after_solve(*args, **kwargs):
            output = solve(*args, **kwargs)
            with Session(self.engine) as db:
                room = db.get(Room, "room-1")
                assert room is not None
                room.agent_input_revision += 1
                db.commit()
            return output

        with patch("services.agent_worker.run_agent_solver", mutate_after_solve):
            result = execute_agent_run(claim, lambda: Session(self.engine))
        self.assertEqual(result.status, "STALE")
        with Session(self.engine) as db:
            self.assertEqual(
                db.scalar(
                    select(func.count()).select_from(AgentCandidate).where(
                        AgentCandidate.run_id == run.run_id
                    )
                ),
                0,
            )

    def test_worker_rolls_back_partial_candidate_write_on_persistence_failure(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-atomic"
        )
        self.assertIsNotNone(claim)
        assert claim is not None
        from services import agent_worker

        store_candidates = agent_worker._store_candidates

        def store_then_fail(*args, **kwargs):
            store_candidates(*args, **kwargs)
            args[0].flush()
            raise AgentCandidateValidationError("simulated transactional failure")

        with patch("services.agent_worker._store_candidates", store_then_fail):
            result = execute_agent_run(claim, lambda: Session(self.engine))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_code, "CANDIDATE_VALIDATION_FAILED")
        with Session(self.engine) as db:
            self.assertEqual(
                db.scalar(
                    select(func.count()).select_from(AgentCandidate).where(
                        AgentCandidate.run_id == run.run_id
                    )
                ),
                0,
            )
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(AgentCandidateMember)
                    .join(
                        AgentCandidate,
                        AgentCandidateMember.candidate_id == AgentCandidate.id,
                    )
                    .where(AgentCandidate.run_id == run.run_id)
                ),
                0,
            )

    def test_worker_rejects_candidate_with_wrong_snapshot_hash_before_inserts(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-bad-candidate"
        )
        self.assertIsNotNone(claim)
        assert claim is not None
        from potato_agent.models import AgentStatus
        from services.agent_solver import AgentSolverOutput

        valid = run_agent_solver(
            claim.run,
            session_factory=lambda: Session(self.engine),
            expected_status="RUNNING",
        )
        invalid_candidate = valid.candidates[0].model_copy(
            update={"source_snapshot_hash": "0" * 64}
        )
        invalid_output = AgentSolverOutput(
            run_id=valid.run_id,
            meeting_id=valid.meeting_id,
            source_revision=valid.source_revision,
            input_snapshot_hash=valid.input_snapshot_hash,
            status=AgentStatus.ALL_AVAILABLE,
            candidates=(invalid_candidate,),
            all_solver_status=valid.all_solver_status,
            solve_time_seconds=valid.solve_time_seconds,
        )
        with patch("services.agent_worker.run_agent_solver", return_value=invalid_output):
            result = execute_agent_run(claim, lambda: Session(self.engine))
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error_code, "CANDIDATE_VALIDATION_FAILED")
        with Session(self.engine) as db:
            self.assertEqual(
                db.scalar(
                    select(func.count()).select_from(AgentCandidate).where(
                        AgentCandidate.run_id == run.run_id
                    )
                ),
                0,
            )

    def test_worker_reclaims_expired_lease_and_rejects_late_old_owner_result(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        first_claim = claim_next_agent_run(
            lambda: Session(self.engine),
            worker_id="worker-old",
            lease_seconds=30,
        )
        self.assertIsNotNone(first_claim)
        assert first_claim is not None
        with Session(self.engine) as db:
            stored = db.get(AgentRun, run.run_id)
            assert stored is not None
            stored.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        second_claim = claim_next_agent_run(
            lambda: Session(self.engine),
            worker_id="worker-new",
            lease_seconds=30,
        )
        self.assertIsNotNone(second_claim)
        assert second_claim is not None
        self.assertEqual(second_claim.run.status, "RUNNING")
        with Session(self.engine) as db:
            stored = db.get(AgentRun, run.run_id)
            assert stored is not None
            self.assertEqual(stored.attempt_number, 2)
            self.assertEqual(stored.worker_id, "worker-new")

        with self.assertRaises(WorkerLeaseLostError):
            execute_agent_run(first_claim, lambda: Session(self.engine))
        result = execute_agent_run(second_claim, lambda: Session(self.engine))
        self.assertEqual(result.status, "ALL_AVAILABLE")

    def test_worker_persists_unknown_failure_and_allows_bounded_retry(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-retry"
        )
        self.assertIsNotNone(claim)
        assert claim is not None

        def unknown(*args, **kwargs):
            from services.agent_solver import AgentSolverUnknownError

            raise AgentSolverUnknownError("solver status UNKNOWN")

        with patch("services.agent_worker.run_agent_solver", unknown):
            failed = execute_agent_run(claim, lambda: Session(self.engine))
        self.assertEqual(failed.status, "FAILED")
        self.assertEqual(failed.error_code, "SOLVER_UNKNOWN")
        self.assertTrue(
            retry_failed_agent_run(lambda: Session(self.engine), run_id=run.run_id)
        )
        retry_claim = claim_next_agent_run(
            lambda: Session(self.engine), worker_id="worker-retry-2"
        )
        self.assertIsNotNone(retry_claim)
        assert retry_claim is not None
        self.assertEqual(retry_claim.run.run_id, run.run_id)
        self.assertEqual(retry_claim.run.status, "RUNNING")
        with Session(self.engine) as db:
            stored = db.get(AgentRun, run.run_id)
            assert stored is not None
            self.assertEqual(stored.attempt_number, 2)

    def test_worker_marks_expired_lease_failed_at_retry_limit(self):
        run = self._create_solver_run(no_submission_start_minute=540)
        claim = claim_next_agent_run(
            lambda: Session(self.engine),
            worker_id="worker-last-attempt",
            lease_seconds=30,
            max_attempts=1,
        )
        self.assertIsNotNone(claim)
        with Session(self.engine) as db:
            stored = db.get(AgentRun, run.run_id)
            assert stored is not None
            stored.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        self.assertIsNone(
            claim_next_agent_run(
                lambda: Session(self.engine),
                worker_id="worker-no-retry",
                lease_seconds=30,
                max_attempts=1,
            )
        )
        with Session(self.engine) as db:
            stored = db.get(AgentRun, run.run_id)
            assert stored is not None
            self.assertEqual(stored.status, "FAILED")
            self.assertEqual(stored.error_code, "WORKER_LEASE_EXHAUSTED")
            self.assertIsNone(stored.worker_id)


if __name__ == "__main__":
    unittest.main()
