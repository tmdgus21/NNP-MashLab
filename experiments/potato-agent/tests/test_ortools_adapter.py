from datetime import date
import threading

import pytest

from potato_agent.candidate_validator import validate_solver_candidates
from potato_agent.fixtures import SAMPLE_DATE, raw_candidate, sample_snapshot
from potato_agent.graph import AgentStatus, open_local_graph
from potato_agent.models import (
    AbsoluteTimeWindow,
    AvailabilitySlot,
    AvailabilityStatus,
    AvailabilitySubmission,
    EligibilityStatus,
    InvitationStatus,
    MeetingSnapshot,
    Participant,
    ParticipantRole,
    RecommendationType,
    ResponseStatus,
    SolverResult,
    SolverStatus,
)
from potato_agent.ortools_adapter import CpSatSolverAdapter


def _snapshot(
    slot_ranges: dict[str, tuple[tuple[int, int], ...]],
    *,
    duration_minutes: int = 60,
    minimum_attendee_count: int = 2,
    dates: tuple[date, ...] = (SAMPLE_DATE,),
    absolute_time_windows: tuple[AbsoluteTimeWindow, ...] = (),
) -> MeetingSnapshot:
    participant_ids = tuple(slot_ranges)
    participants = tuple(
        Participant(
            participant_id=participant_id,
            display_name=participant_id,
            role=(
                ParticipantRole.ORGANIZER
                if index == 0
                else ParticipantRole.INVITEE
            ),
            invitation_status=(
                InvitationStatus.NOT_APPLICABLE
                if index == 0
                else InvitationStatus.SENT
            ),
            response_status=ResponseStatus.ACCEPTED,
            eligibility_status=EligibilityStatus.ACTIVE,
        )
        for index, participant_id in enumerate(participant_ids)
    )
    availability = {
        participant_id: AvailabilitySubmission(
            participant_id=participant_id,
            status=AvailabilityStatus.SUBMITTED,
            slots=tuple(
                AvailabilitySlot(
                    date=meeting_date,
                    start_minute=start,
                    end_minute=end,
                )
                for meeting_date in dates
                for start, end in ranges
            ),
            submission_version=1,
        )
        for participant_id, ranges in slot_ranges.items()
    }
    return MeetingSnapshot(
        meeting_id="ortools-meeting",
        agent_session_id="ortools-session",
        run_id="ortools-run",
        input_revision=7,
        input_snapshot_hash="ortools-snapshot-v7",
        consent_round=1,
        title="CP-SAT test meeting",
        activity="Test",
        location="Local",
        duration_minutes=duration_minutes,
        dates=dates,
        minimum_attendee_count=minimum_attendee_count,
        absolute_time_windows=absolute_time_windows,
        participants=participants,
        availability_by_participant_id=availability,
    )


def _uniform_snapshot(participant_count: int, **kwargs) -> MeetingSnapshot:
    return _snapshot(
        {
            ("organizer" if index == 0 else f"member-{index}"): ((600, 720),)
            for index in range(participant_count)
        },
        **kwargs,
    )


@pytest.mark.parametrize("participant_count", [2, 5])
def test_actual_cp_sat_finds_all_attendee_candidates(participant_count):
    snapshot = _uniform_snapshot(participant_count)
    adapter = CpSatSolverAdapter(snapshot)

    result = adapter.solve_all_attendees(snapshot)

    assert result.status == SolverStatus.OPTIMAL
    assert [candidate.start_minute for candidate in result.candidates] == [
        600,
        601,
        602,
    ]
    assert all(
        len(candidate.attendee_ids) == participant_count
        for candidate in result.candidates
    )


def test_partial_solver_proves_maximum_four_of_five():
    snapshot = _snapshot(
        {
            "organizer": ((600, 660),),
            "member-1": ((600, 660),),
            "member-2": ((600, 660),),
            "member-3": ((600, 660),),
            "member-4": ((660, 720),),
        },
        minimum_attendee_count=3,
    )
    adapter = CpSatSolverAdapter(snapshot)

    all_result = adapter.solve_all_attendees(snapshot)
    partial_result = adapter.solve_partial_attendees(
        snapshot, snapshot.minimum_attendee_count
    )

    assert all_result.status == SolverStatus.INFEASIBLE
    assert partial_result.status == SolverStatus.OPTIMAL
    assert partial_result.maximum_attendees_proven is True
    assert len(partial_result.candidates[0].attendee_ids) == 4
    assert partial_result.candidates[0].unavailable_ids == ("member-4",)


def test_real_cp_sat_graph_validates_proven_maximum_partial_candidate(tmp_path):
    snapshot = _snapshot(
        {
            "organizer": ((600, 660),),
            "member-1": ((600, 660),),
            "member-2": ((600, 660),),
            "member-3": ((600, 660),),
            "member-4": ((660, 720),),
        },
        minimum_attendee_count=3,
    )
    adapter = CpSatSolverAdapter(snapshot)
    config = {"configurable": {"thread_id": "cp-sat:maximum-partial"}}

    with open_local_graph(adapter, tmp_path / "maximum-partial.sqlite") as graph:
        result = graph.invoke({"meeting_id": snapshot.meeting_id}, config=config)

    payload = result["__interrupt__"][0].value
    candidate = payload["candidates"][0]
    assert result["status"] == AgentStatus.PARTIAL_ALTERNATIVE
    assert len(candidate["attendee_ids"]) == 4
    assert candidate["unavailable_ids"] == ["member-4"]
    assert candidate["maximum_attendees_proven"] is True


def test_partial_solver_returns_infeasible_when_best_count_is_below_minimum():
    snapshot = _snapshot(
        {
            "organizer": ((600, 660),),
            "member-1": ((600, 660),),
            "member-2": ((600, 660),),
            "member-3": ((660, 720),),
            "member-4": ((720, 780),),
        },
        minimum_attendee_count=4,
    )
    adapter = CpSatSolverAdapter(snapshot)

    all_result = adapter.solve_all_attendees(snapshot)
    partial_result = adapter.solve_partial_attendees(snapshot, 4)

    assert all_result.status == SolverStatus.INFEASIBLE
    assert partial_result.status == SolverStatus.INFEASIBLE
    assert partial_result.candidates == ()


def test_graph_routes_real_cp_sat_infeasibility_to_partial_search(tmp_path):
    snapshot = _snapshot(
        {
            "organizer": ((600, 660),),
            "member-1": ((600, 660),),
            "member-2": ((660, 720),),
        },
        minimum_attendee_count=3,
    )
    adapter = CpSatSolverAdapter(snapshot)
    config = {
        "configurable": {
            "thread_id": "cp-sat:actual-partial-route",
        }
    }

    with open_local_graph(adapter, tmp_path / "cp-sat.sqlite") as graph:
        result = graph.invoke({"meeting_id": snapshot.meeting_id}, config=config)

    assert result["status"] == AgentStatus.NO_FEASIBLE_SCHEDULE


def test_real_cp_sat_candidates_pass_graph_validator(tmp_path):
    snapshot = _uniform_snapshot(5)
    adapter = CpSatSolverAdapter(snapshot)
    config = {"configurable": {"thread_id": "cp-sat:verified-candidate"}}

    with open_local_graph(adapter, tmp_path / "verified.sqlite") as graph:
        result = graph.invoke({"meeting_id": snapshot.meeting_id}, config=config)

    payload = result["__interrupt__"][0].value
    assert result["status"] == AgentStatus.ALL_AVAILABLE
    assert payload["kind"] == "candidate_selection"
    assert payload["candidates"][0]["verified"] is True
    assert payload["candidates"][0]["maximum_attendees_proven"] is True


def test_touching_availability_intervals_form_a_continuous_slot():
    snapshot = _snapshot(
        {
            "organizer": ((600, 630), (630, 660)),
            "member-1": ((600, 660),),
        }
    )

    result = CpSatSolverAdapter(snapshot).solve_all_attendees(snapshot)

    assert result.status == SolverStatus.OPTIMAL
    assert result.candidates[0].start_minute == 600
    assert result.candidates[0].end_minute == 660


def test_end_of_day_boundary_preserves_exact_minutes():
    snapshot = _snapshot(
        {
            "organizer": ((1410, 1440),),
            "member-1": ((1410, 1440),),
        },
        duration_minutes=30,
    )

    result = CpSatSolverAdapter(snapshot).solve_all_attendees(snapshot)

    assert result.status == SolverStatus.OPTIMAL
    assert result.candidates[0].start_minute == 1410
    assert result.candidates[0].end_minute == 1440


def test_no_interval_shorter_than_duration_is_accepted():
    snapshot = _snapshot(
        {
            "organizer": ((600, 659),),
            "member-1": ((600, 660),),
        }
    )

    result = CpSatSolverAdapter(snapshot).solve_all_attendees(snapshot)

    assert result.status == SolverStatus.INFEASIBLE
    assert result.candidates == ()


def test_multiple_disjoint_absolute_windows_are_treated_as_allowed_union():
    snapshot = _uniform_snapshot(
        2,
        absolute_time_windows=(
            AbsoluteTimeWindow(
                date=SAMPLE_DATE, start_minute=600, end_minute=660
            ),
            AbsoluteTimeWindow(
                date=SAMPLE_DATE, start_minute=720, end_minute=780
            ),
        ),
    )
    snapshot = snapshot.model_copy(
        update={
            "availability_by_participant_id": {
                participant_id: submission.model_copy(
                    update={
                        "slots": (
                            AvailabilitySlot(
                                date=SAMPLE_DATE,
                                start_minute=720,
                                end_minute=780,
                            ),
                        )
                    }
                )
                for participant_id, submission
                in snapshot.availability_by_participant_id.items()
            }
        }
    )

    result = CpSatSolverAdapter(snapshot).solve_all_attendees(snapshot)

    assert result.status == SolverStatus.OPTIMAL
    assert result.candidates[0].start_minute == 720


def test_same_attendance_candidates_have_deterministic_order():
    snapshot = _uniform_snapshot(5)
    adapter = CpSatSolverAdapter(snapshot)

    first = adapter.solve_partial_attendees(snapshot, 2)
    second = adapter.solve_partial_attendees(snapshot, 2)

    first_keys = [
        (candidate.date, candidate.start_minute, candidate.attendee_ids)
        for candidate in first.candidates
    ]
    second_keys = [
        (candidate.date, candidate.start_minute, candidate.attendee_ids)
        for candidate in second.candidates
    ]
    assert first.status == second.status == SolverStatus.OPTIMAL
    assert first.maximum_attendees_proven is True
    assert first_keys == second_keys == [
        (SAMPLE_DATE, 600, tuple(sorted(snapshot.availability_by_participant_id))),
        (SAMPLE_DATE, 601, tuple(sorted(snapshot.availability_by_participant_id))),
        (SAMPLE_DATE, 602, tuple(sorted(snapshot.availability_by_participant_id))),
    ]


def test_disjoint_available_intervals_both_produce_candidates():
    snapshot = _snapshot(
        {
            "organizer": ((600, 660), (720, 780)),
            "member-1": ((600, 660), (720, 780)),
        }
    )

    result = CpSatSolverAdapter(snapshot).solve_all_attendees(snapshot)

    assert result.status == SolverStatus.OPTIMAL
    assert [candidate.start_minute for candidate in result.candidates] == [600, 720]


def test_revision_mismatch_is_stale_not_infeasible():
    snapshot = _uniform_snapshot(2)
    adapter = CpSatSolverAdapter(
        snapshot,
        revision_provider=lambda _: snapshot.input_revision + 1,
    )

    result = adapter.solve_all_attendees(snapshot)

    assert result.status == SolverStatus.STALE
    assert result.candidates == ()


def test_revision_change_during_candidate_enumeration_is_stale():
    snapshot = _uniform_snapshot(2)
    revisions = iter((snapshot.input_revision, snapshot.input_revision + 1))
    adapter = CpSatSolverAdapter(snapshot, revision_provider=lambda _: next(revisions))

    result = adapter.solve_all_attendees(snapshot)

    assert result.status == SolverStatus.STALE
    assert result.candidates == ()


def test_pre_cancelled_solver_returns_cancelled_not_infeasible():
    snapshot = _uniform_snapshot(2)
    cancellation = threading.Event()
    cancellation.set()

    result = CpSatSolverAdapter(
        snapshot, cancellation_event=cancellation
    ).solve_all_attendees(snapshot)

    assert result.status == SolverStatus.CANCELLED
    assert result.candidates == ()


def test_cancelled_solver_stops_graph_without_partial_fallback(tmp_path):
    snapshot = _snapshot(
        {
            "organizer": ((600, 660),),
            "member-1": ((600, 660),),
            "member-2": ((660, 720),),
        },
        minimum_attendee_count=2,
    )
    cancellation = threading.Event()
    cancellation.set()
    adapter = CpSatSolverAdapter(snapshot, cancellation_event=cancellation)
    config = {"configurable": {"thread_id": "cp-sat:cancelled"}}

    with open_local_graph(adapter, tmp_path / "cancelled.sqlite") as graph:
        result = graph.invoke({"meeting_id": snapshot.meeting_id}, config=config)

    assert result["status"] == AgentStatus.CANCELLED
    assert result["error"]["code"] == "SOLVER_CANCELLED"


def test_solver_time_limit_never_becomes_infeasible():
    snapshot = _uniform_snapshot(2)
    adapter = CpSatSolverAdapter(snapshot, time_limit_seconds=1e-9)

    result = adapter.solve_all_attendees(snapshot)

    assert result.status == SolverStatus.TIMEOUT
    assert result.candidates == ()


def test_independent_validator_rejects_candidate_with_wrong_snapshot_hash():
    snapshot = sample_snapshot()
    candidate = raw_candidate(snapshot)
    candidate = candidate.model_copy(
        update={"source_snapshot_hash": "different-input-version"}
    )
    result = SolverResult(
        status=SolverStatus.OPTIMAL,
        candidates=(candidate,),
        maximum_attendees_proven=True,
    )

    with pytest.raises(ValueError, match="snapshot hash"):
        validate_solver_candidates(
            snapshot,
            result,
            RecommendationType.ALL_AVAILABLE,
            SolverStatus.OPTIMAL,
            snapshot.input_revision,
        )
