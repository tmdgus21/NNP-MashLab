"""Explicit local-only fixtures; these are not AI or optimizer results."""

from datetime import date

from potato_agent.models import (
    AvailabilitySlot,
    AvailabilityStatus,
    AvailabilitySubmission,
    EligibilityStatus,
    InvitationStatus,
    MeetingSnapshot,
    Participant,
    ParticipantRole,
    RawCandidate,
    RecommendationType,
    ResponseStatus,
    SolverResult,
    SolverStatus,
)

SAMPLE_DATE = date(2026, 11, 8)


def sample_snapshot() -> MeetingSnapshot:
    participant_ids = ("organizer-1", "invitee-1", "invitee-2")
    participants = (
        Participant(
            participant_id=participant_ids[0],
            display_name="Organizer fixture",
            role=ParticipantRole.ORGANIZER,
            invitation_status=InvitationStatus.NOT_APPLICABLE,
            response_status=ResponseStatus.ACCEPTED,
            eligibility_status=EligibilityStatus.ACTIVE,
        ),
        *(
            Participant(
                participant_id=participant_id,
                display_name=f"Invitee fixture {index}",
                role=ParticipantRole.INVITEE,
                invitation_status=InvitationStatus.SENT,
                response_status=ResponseStatus.ACCEPTED,
                eligibility_status=EligibilityStatus.ACTIVE,
            )
            for index, participant_id in enumerate(participant_ids[1:], start=1)
        ),
    )
    availability = {
        participant_id: AvailabilitySubmission(
            participant_id=participant_id,
            status=AvailabilityStatus.SUBMITTED,
            slots=(
                AvailabilitySlot(
                    date=SAMPLE_DATE,
                    start_minute=600,
                    end_minute=660,
                ),
            ),
            submission_version=1,
        )
        for participant_id in participant_ids
    }
    return MeetingSnapshot(
        meeting_id="meeting-fixture",
        agent_session_id="session-fixture",
        run_id="run-fixture",
        input_revision=7,
        input_snapshot_hash="fixture-snapshot-hash-v7",
        consent_round=1,
        title="Local fixture meeting",
        activity="Fixture activity",
        location="Fixture location",
        duration_minutes=60,
        dates=(SAMPLE_DATE,),
        minimum_attendee_count=2,
        participants=participants,
        availability_by_participant_id=availability,
    )


def raw_candidate(
    snapshot: MeetingSnapshot,
    *,
    recommendation_type: RecommendationType = RecommendationType.ALL_AVAILABLE,
    attendee_ids: tuple[str, ...] = ("organizer-1", "invitee-1", "invitee-2"),
    unavailable_ids: tuple[str, ...] = (),
    start_minute: int = 600,
    source_revision: int | None = None,
) -> RawCandidate:
    return RawCandidate(
        meeting_id=snapshot.meeting_id,
        agent_run_id=snapshot.run_id,
        source_revision=(
            snapshot.input_revision if source_revision is None else source_revision
        ),
        source_snapshot_hash=snapshot.input_snapshot_hash,
        date=SAMPLE_DATE,
        start_minute=start_minute,
        end_minute=start_minute + snapshot.duration_minutes,
        time_zone="Asia/Seoul",
        recommendation_type=recommendation_type,
        attendee_ids=attendee_ids,
        unavailable_ids=unavailable_ids,
    )


def all_available_result(snapshot: MeetingSnapshot) -> SolverResult:
    return SolverResult(
        status=SolverStatus.FEASIBLE,
        candidates=(raw_candidate(snapshot),),
    )
