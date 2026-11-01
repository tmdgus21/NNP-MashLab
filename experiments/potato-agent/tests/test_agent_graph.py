import pytest
from langgraph.types import Command
from pydantic import ValidationError

from potato_agent.fixtures import (
    SAMPLE_DATE,
    AvailabilitySlot,
    all_available_result,
    raw_candidate,
    sample_snapshot,
)
from potato_agent.graph import AgentStatus, open_local_graph
from potato_agent.models import (
    AbsoluteTimeWindow,
    AvailabilityStatus,
    AvailabilitySubmission,
    RecommendationType,
    ResponseStatus,
    SolverResult,
    SolverStatus,
)
from potato_agent.tools import FixtureToolAdapter


def _interrupt_payload(result):
    return result["__interrupt__"][0].value


def _thread_config(snapshot):
    return {
        "configurable": {
            "thread_id": f"test:{snapshot.meeting_id}:{snapshot.run_id}"
        }
    }


def _consent_resume(snapshot, candidate_id, participant_id):
    return {
        "participantId": participant_id,
        "candidateId": candidate_id,
        "inputRevision": snapshot.input_revision,
        "consentRound": snapshot.consent_round,
        "decision": "AGREE",
    }


def _partial_candidate(snapshot):
    return raw_candidate(
        snapshot,
        recommendation_type=RecommendationType.PARTIAL_ALTERNATIVE,
        attendee_ids=("organizer-1", "invitee-1"),
        unavailable_ids=("invitee-2",),
    )


def _snapshot_for_partial_search():
    snapshot = sample_snapshot()
    availability = dict(snapshot.availability_by_participant_id)
    availability["invitee-2"] = availability["invitee-2"].model_copy(
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
    return snapshot.model_copy(update={"availability_by_participant_id": availability})


def test_all_attendee_candidate_is_validated_before_selection_interrupt(tmp_path):
    snapshot = sample_snapshot()
    tools = FixtureToolAdapter(snapshot, all_available_result(snapshot))

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    payload = _interrupt_payload(result)
    assert result["status"] == AgentStatus.ALL_AVAILABLE
    assert payload["kind"] == "candidate_selection"
    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["verified"] is True
    assert tools.calls == [("load_snapshot", None), ("solve_all_attendees", None)]


def test_partial_search_runs_only_after_proven_all_infeasible(tmp_path):
    snapshot = _snapshot_for_partial_search()
    tools = FixtureToolAdapter(
        snapshot,
        SolverResult(status=SolverStatus.INFEASIBLE),
        SolverResult(
            status=SolverStatus.FEASIBLE,
            candidates=(_partial_candidate(snapshot),),
        ),
    )

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.PARTIAL_ALTERNATIVE
    assert _interrupt_payload(result)["candidates"][0]["recommendation_type"] == (
        "PARTIAL_ALTERNATIVE"
    )
    assert ("solve_partial_attendees", 2) in tools.calls


@pytest.mark.parametrize(
    ("solver_status", "expected_code"),
    [
        (SolverStatus.UNKNOWN, "SOLVER_UNKNOWN"),
        (SolverStatus.TIMEOUT, "SOLVER_TIMEOUT"),
        (SolverStatus.MODEL_INVALID, "SOLVER_MODEL_INVALID"),
    ],
)
def test_unknown_timeout_and_invalid_model_never_fall_back(
    tmp_path, solver_status, expected_code
):
    snapshot = _snapshot_for_partial_search()
    tools = FixtureToolAdapter(
        snapshot,
        SolverResult(status=solver_status),
        SolverResult(
            status=SolverStatus.FEASIBLE,
            candidates=(_partial_candidate(snapshot),),
        ),
    )

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.ERROR
    assert result["error"]["code"] == expected_code
    assert not any(name == "solve_partial_attendees" for name, _ in tools.calls)


def test_waiting_separates_pending_rsvp_from_missing_availability(tmp_path):
    snapshot = sample_snapshot().model_copy(
        update={
            "participants": (
                sample_snapshot().participants[0],
                sample_snapshot().participants[1],
                sample_snapshot().participants[2].model_copy(
                    update={"response_status": ResponseStatus.PENDING}
                ),
            ),
            "availability_by_participant_id": {
                "invitee-1": AvailabilitySubmission(
                    participant_id="invitee-1",
                    status=AvailabilityStatus.NOT_SUBMITTED,
                )
            },
        }
    )
    tools = FixtureToolAdapter(snapshot, all_available_result(sample_snapshot()))

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.WAITING_FOR_INPUT
    assert result["readiness"].pending_rsvp_ids == ("invitee-2",)
    assert result["readiness"].availability_not_submitted_ids == (
        "organizer-1",
        "invitee-1",
    )
    assert not any(name.startswith("solve_") for name, _ in tools.calls)


def test_partial_candidate_below_host_minimum_is_rejected(tmp_path):
    snapshot = _snapshot_for_partial_search()
    invalid = raw_candidate(
        snapshot,
        recommendation_type=RecommendationType.PARTIAL_ALTERNATIVE,
        attendee_ids=("organizer-1",),
        unavailable_ids=("invitee-1", "invitee-2"),
    )
    tools = FixtureToolAdapter(
        snapshot,
        SolverResult(status=SolverStatus.INFEASIBLE),
        SolverResult(status=SolverStatus.FEASIBLE, candidates=(invalid,)),
    )

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.ERROR
    assert result["error"]["code"] == "CANDIDATE_VALIDATION_FAILED"


def test_all_attendee_candidate_cannot_omit_a_participant(tmp_path):
    snapshot = sample_snapshot()
    invalid = raw_candidate(
        snapshot,
        attendee_ids=("organizer-1", "invitee-1"),
    )
    tools = FixtureToolAdapter(
        snapshot,
        SolverResult(status=SolverStatus.FEASIBLE, candidates=(invalid,)),
    )

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.ERROR
    assert result["candidates"] == []


def test_candidate_outside_absolute_time_window_is_rejected(tmp_path):
    snapshot = sample_snapshot().model_copy(
        update={
            "absolute_time_windows": (
                AbsoluteTimeWindow(
                    date=SAMPLE_DATE,
                    start_minute=720,
                    end_minute=840,
                ),
            )
        }
    )
    tools = FixtureToolAdapter(snapshot, all_available_result(sample_snapshot()))

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.ERROR
    assert result["error"]["code"] == "CANDIDATE_VALIDATION_FAILED"


def test_revision_change_during_solve_marks_run_stale_without_fallback(tmp_path):
    snapshot = sample_snapshot()
    tools = FixtureToolAdapter(
        snapshot,
        SolverResult(status=SolverStatus.INFEASIBLE),
        SolverResult(status=SolverStatus.INFEASIBLE),
        revision_after_all=snapshot.input_revision + 1,
    )

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.STALE
    assert not any(name == "solve_partial_attendees" for name, _ in tools.calls)


def test_old_candidate_revision_is_rejected(tmp_path):
    snapshot = sample_snapshot()
    stale_candidate = raw_candidate(snapshot, source_revision=snapshot.input_revision - 1)
    tools = FixtureToolAdapter(
        snapshot,
        SolverResult(status=SolverStatus.FEASIBLE, candidates=(stale_candidate,)),
    )

    with open_local_graph(tools, tmp_path / "checkpoints.sqlite") as graph:
        result = graph.invoke(
            {"meeting_id": snapshot.meeting_id},
            config=_thread_config(snapshot),
        )

    assert result["status"] == AgentStatus.ERROR
    assert result["error"]["code"] == "CANDIDATE_VALIDATION_FAILED"


def test_sqlite_checkpoint_resumes_selection_consent_and_host_approval(
    tmp_path, caplog
):
    snapshot = sample_snapshot()
    tools = FixtureToolAdapter(snapshot, all_available_result(snapshot))
    checkpoint_path = tmp_path / "persistent.sqlite"
    config = _thread_config(snapshot)

    with open_local_graph(tools, checkpoint_path) as graph:
        first = graph.invoke({"meeting_id": snapshot.meeting_id}, config=config)
    first_pause = _interrupt_payload(first)
    candidate_id = first_pause["candidates"][0]["candidate_id"]

    with open_local_graph(tools, checkpoint_path) as graph:
        consent_pause = graph.invoke(
            Command(
                resume={
                    "candidateId": candidate_id,
                    "inputRevision": snapshot.input_revision,
                }
            ),
            config=config,
        )
    first_consent_payload = _interrupt_payload(consent_pause)
    assert first_consent_payload["kind"] == "participant_consents"
    assert first_consent_payload["attendeeIds"] == [
        "invitee-1",
        "invitee-2",
        "organizer-1",
    ]

    with open_local_graph(tools, checkpoint_path) as graph:
        second_consent_pause = graph.invoke(
            Command(
                resume=_consent_resume(snapshot, candidate_id, "organizer-1")
            ),
            config=config,
        )
    consent_payload = _interrupt_payload(second_consent_pause)
    assert consent_payload["kind"] == "participant_consents"
    assert consent_payload["alreadyConsentedIds"] == ["organizer-1"]

    with open_local_graph(tools, checkpoint_path) as graph:
        third_consent_pause = graph.invoke(
            Command(
                resume=_consent_resume(snapshot, candidate_id, "invitee-1")
            ),
            config=config,
        )
    assert _interrupt_payload(third_consent_pause)["alreadyConsentedIds"] == [
        "invitee-1",
        "organizer-1",
    ]

    with open_local_graph(tools, checkpoint_path) as graph:
        approval_pause = graph.invoke(
            Command(
                resume=_consent_resume(snapshot, candidate_id, "invitee-2")
            ),
            config=config,
        )
    assert _interrupt_payload(approval_pause)["kind"] == "host_approval"

    with open_local_graph(tools, checkpoint_path) as graph:
        approved = graph.invoke(
            Command(
                resume={
                    "actorParticipantId": "organizer-1",
                    "candidateId": candidate_id,
                    "inputRevision": snapshot.input_revision,
                    "consentRound": snapshot.consent_round,
                    "decision": "APPROVE",
                }
            ),
            config=config,
        )

    assert approved["approval_decision"] == "APPROVED"
    assert approved["status"] == AgentStatus.AWAITING_APPROVAL
    assert approved["meeting_finalized"] is False
    assert "unregistered type" not in caplog.text


def test_invalid_minimum_attendance_is_rejected():
    payload = sample_snapshot().model_dump()
    payload["minimum_attendee_count"] = 1
    with pytest.raises(ValidationError):
        type(sample_snapshot()).model_validate(payload)


def test_unsubmitted_availability_cannot_contain_slots():
    with pytest.raises(ValidationError):
        AvailabilitySubmission(
            participant_id="invitee-1",
            status=AvailabilityStatus.NOT_SUBMITTED,
            slots=(
                {
                    "date": SAMPLE_DATE,
                    "start_minute": 600,
                    "end_minute": 660,
                },
            ),
        )
