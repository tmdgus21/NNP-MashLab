from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    model_validator,
)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InvitationStatus(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_SENT = "NOT_SENT"
    SENT = "SENT"


class ResponseStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class EligibilityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXCLUDED_BY_HOST = "EXCLUDED_BY_HOST"


class ParticipantRole(StrEnum):
    ORGANIZER = "ORGANIZER"
    INVITEE = "INVITEE"


class AvailabilityStatus(StrEnum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    MODEL_INVALID = "MODEL_INVALID"
    NOT_RUN = "NOT_RUN"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


class RecommendationType(StrEnum):
    ALL_AVAILABLE = "ALL_AVAILABLE"
    PARTIAL_ALTERNATIVE = "PARTIAL_ALTERNATIVE"


class ConsentDecision(StrEnum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"


class HostDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class AgentStatus(StrEnum):
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    ANALYZING = "ANALYZING"
    RUNNING_TOOLS = "RUNNING_TOOLS"
    ALL_AVAILABLE = "ALL_AVAILABLE"
    PARTIAL_ALTERNATIVE = "PARTIAL_ALTERNATIVE"
    NO_FEASIBLE_SCHEDULE = "NO_FEASIBLE_SCHEDULE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    STALE = "STALE"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class Participant(DomainModel):
    participant_id: StrictStr
    display_name: StrictStr
    role: ParticipantRole
    invitation_status: InvitationStatus
    response_status: ResponseStatus
    eligibility_status: EligibilityStatus = EligibilityStatus.ACTIVE

    @model_validator(mode="after")
    def validate_response_state(self) -> Participant:
        if self.role == ParticipantRole.ORGANIZER:
            if self.response_status != ResponseStatus.ACCEPTED:
                raise ValueError("The organizer must be accepted.")
            if self.eligibility_status != EligibilityStatus.ACTIVE:
                raise ValueError("The organizer cannot be excluded.")
            if self.invitation_status != InvitationStatus.NOT_APPLICABLE:
                raise ValueError("The organizer has no invitation status.")
        elif self.response_status in (ResponseStatus.PENDING, ResponseStatus.DECLINED):
            if self.invitation_status != InvitationStatus.SENT:
                raise ValueError("Pending or declined invitees must have a sent invitation.")
        return self


class AvailabilitySlot(DomainModel):
    date: date
    start_minute: Annotated[StrictInt, Field(ge=0, le=1439)]
    end_minute: Annotated[StrictInt, Field(ge=1, le=1440)]
    time_zone: Literal["Asia/Seoul"] = "Asia/Seoul"

    @model_validator(mode="after")
    def validate_interval(self) -> AvailabilitySlot:
        if self.start_minute >= self.end_minute:
            raise ValueError("Availability slots must use a non-empty half-open interval.")
        return self


class AvailabilitySubmission(DomainModel):
    participant_id: StrictStr
    status: AvailabilityStatus
    slots: tuple[AvailabilitySlot, ...] = ()
    time_zone: Literal["Asia/Seoul"] = "Asia/Seoul"
    submitted_at: datetime | None = None
    updated_at: datetime | None = None
    submission_version: Annotated[StrictInt, Field(ge=0)] = 0

    @model_validator(mode="after")
    def validate_submission(self) -> AvailabilitySubmission:
        if self.status == AvailabilityStatus.NOT_SUBMITTED and self.slots:
            raise ValueError("An unsubmitted availability cannot contain slots.")
        if self.status == AvailabilityStatus.SUBMITTED and not self.slots:
            raise ValueError("A submitted availability must contain at least one slot.")
        return self


class AbsoluteTimeWindow(DomainModel):
    """Supported local fixture constraint; no broader constraint DSL is implied."""

    date: date
    start_minute: Annotated[StrictInt, Field(ge=0, le=1439)]
    end_minute: Annotated[StrictInt, Field(ge=1, le=1440)]

    @model_validator(mode="after")
    def validate_interval(self) -> AbsoluteTimeWindow:
        if self.start_minute >= self.end_minute:
            raise ValueError("Absolute time windows must be non-empty.")
        return self


class MeetingSnapshot(DomainModel):
    meeting_id: StrictStr
    agent_session_id: StrictStr
    run_id: StrictStr
    input_revision: Annotated[StrictInt, Field(ge=0)]
    input_snapshot_hash: StrictStr
    consent_round: Annotated[StrictInt, Field(ge=1)]
    title: StrictStr
    activity: StrictStr
    location: StrictStr
    duration_minutes: Annotated[StrictInt, Field(gt=0, le=1440)]
    dates: tuple[date, ...]
    excluded_dates: tuple[date, ...] = ()
    time_zone: Literal["Asia/Seoul"] = "Asia/Seoul"
    minimum_attendee_count: Annotated[StrictInt, Field(ge=2)]
    required_start_minutes_by_date: dict[
        date, Annotated[StrictInt, Field(ge=0, le=1439)]
    ] = Field(default_factory=dict)
    absolute_time_windows: tuple[AbsoluteTimeWindow, ...] = ()
    participants: tuple[Participant, ...]
    availability_by_participant_id: dict[str, AvailabilitySubmission]

    @model_validator(mode="after")
    def validate_roster_and_availability(self) -> MeetingSnapshot:
        participant_ids = [participant.participant_id for participant in self.participants]
        if len(participant_ids) != len(set(participant_ids)):
            raise ValueError("Participant IDs must be unique.")

        organizers = [p for p in self.participants if p.role == ParticipantRole.ORGANIZER]
        if len(organizers) != 1:
            raise ValueError("A meeting must have exactly one organizer.")

        eligible = [
            p
            for p in self.participants
            if p.role == ParticipantRole.ORGANIZER
            or (
                p.response_status == ResponseStatus.ACCEPTED
                and p.eligibility_status == EligibilityStatus.ACTIVE
            )
        ]
        if len(eligible) < 2:
            raise ValueError("The MVP requires at least two eligible participants.")
        if self.minimum_attendee_count > len(eligible):
            raise ValueError("The configured minimum exceeds the eligible participant count.")
        if len(self.dates) != len(set(self.dates)):
            raise ValueError("Meeting dates must be unique.")
        if len(self.excluded_dates) != len(set(self.excluded_dates)):
            raise ValueError("Excluded meeting dates must be unique.")
        if set(self.excluded_dates) - set(self.dates):
            raise ValueError("Only configured meeting dates can be excluded.")
        if set(self.required_start_minutes_by_date) - set(self.dates):
            raise ValueError("Exact start times must use configured meeting dates.")
        if any(
            minute + self.duration_minutes > 1440
            for minute in self.required_start_minutes_by_date.values()
        ):
            raise ValueError("Exact meeting times cannot extend beyond midnight.")
        if any(window.date not in self.dates for window in self.absolute_time_windows):
            raise ValueError("Absolute time windows must use an allowed meeting date.")

        roster = set(participant_ids)
        if set(self.availability_by_participant_id) - roster:
            raise ValueError("Availability references an unknown participant.")
        for participant_id, submission in self.availability_by_participant_id.items():
            if submission.participant_id != participant_id:
                raise ValueError("Availability map keys must match participant IDs.")
            if any(slot.date not in self.dates for slot in submission.slots):
                raise ValueError("Availability slots must use an allowed meeting date.")
        return self


class ReadinessReport(DomainModel):
    pending_rsvp_ids: tuple[str, ...] = ()
    availability_not_submitted_ids: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.pending_rsvp_ids and not self.availability_not_submitted_ids


class RawCandidate(DomainModel):
    meeting_id: StrictStr
    agent_run_id: StrictStr
    source_revision: Annotated[StrictInt, Field(ge=0)]
    source_snapshot_hash: StrictStr
    date: date
    start_minute: Annotated[StrictInt, Field(ge=0, le=1439)]
    end_minute: Annotated[StrictInt, Field(ge=1, le=1440)]
    time_zone: Literal["Asia/Seoul"]
    recommendation_type: RecommendationType
    attendee_ids: tuple[StrictStr, ...]
    unavailable_ids: tuple[StrictStr, ...]


class SolverResult(DomainModel):
    status: SolverStatus
    candidates: tuple[RawCandidate, ...] = ()
    maximum_attendees_proven: bool = False
    solve_time_seconds: float = Field(default=0.0, ge=0.0)
    diagnostic: StrictStr | None = None


class Candidate(DomainModel):
    candidate_id: StrictStr
    meeting_id: StrictStr
    agent_run_id: StrictStr
    source_revision: Annotated[StrictInt, Field(ge=0)]
    source_snapshot_hash: StrictStr
    date: date
    start_minute: Annotated[StrictInt, Field(ge=0, le=1439)]
    end_minute: Annotated[StrictInt, Field(ge=1, le=1440)]
    time_zone: Literal["Asia/Seoul"]
    recommendation_type: RecommendationType
    attendee_ids: tuple[StrictStr, ...]
    unavailable_ids: tuple[StrictStr, ...]
    solver_status: Literal[SolverStatus.OPTIMAL, SolverStatus.FEASIBLE]
    maximum_attendees_proven: bool = False
    verified: Literal[True] = True
    explanation: StrictStr

    @model_validator(mode="after")
    def validate_interval(self) -> Candidate:
        if self.start_minute >= self.end_minute:
            raise ValueError("Candidate interval must be non-empty.")
        return self


class CandidateSelection(DomainModel):
    candidate_id: StrictStr = Field(validation_alias="candidateId")
    input_revision: Annotated[StrictInt, Field(ge=0)] = Field(
        validation_alias="inputRevision"
    )


class ConsentSubmission(DomainModel):
    participant_id: StrictStr = Field(validation_alias="participantId")
    candidate_id: StrictStr = Field(validation_alias="candidateId")
    input_revision: Annotated[StrictInt, Field(ge=0)] = Field(
        validation_alias="inputRevision"
    )
    consent_round: Annotated[StrictInt, Field(ge=1)] = Field(
        validation_alias="consentRound"
    )
    decision: ConsentDecision


class HostApprovalSubmission(DomainModel):
    actor_participant_id: StrictStr = Field(validation_alias="actorParticipantId")
    candidate_id: StrictStr = Field(validation_alias="candidateId")
    input_revision: Annotated[StrictInt, Field(ge=0)] = Field(
        validation_alias="inputRevision"
    )
    consent_round: Annotated[StrictInt, Field(ge=1)] = Field(
        validation_alias="consentRound"
    )
    decision: HostDecision
