from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, StrictInt, StrictStr, model_validator

from potato_agent.models import (
    AbsoluteTimeWindow,
    AvailabilitySlot,
    AvailabilityStatus,
    AvailabilitySubmission,
    DomainModel,
    EligibilityStatus,
    MeetingSnapshot,
    ParticipantRole,
    ResponseStatus,
)


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    REJECTED = "REJECTED"


class ProposalScope(StrEnum):
    MEETING_CONSTRAINT = "MEETING_CONSTRAINT"
    PERSONAL_AVAILABILITY = "PERSONAL_AVAILABILITY"


class RescheduleChangeBase(DomainModel):
    kind: str


class SetMeetingDatesChange(RescheduleChangeBase):
    kind: Literal["SET_MEETING_DATES"]
    dates: tuple[date, ...] = Field(min_length=1)


class SetStartTimeChange(RescheduleChangeBase):
    kind: Literal["SET_START_TIME"]
    date: date
    minute: Annotated[StrictInt, Field(ge=0, le=1439)]


class SetEndTimeChange(RescheduleChangeBase):
    kind: Literal["SET_END_TIME"]
    date: date
    minute: Annotated[StrictInt, Field(ge=1, le=1440)]


class SetDurationChange(RescheduleChangeBase):
    kind: Literal["SET_DURATION"]
    duration_minutes: Annotated[StrictInt, Field(gt=0, le=1440)]


class ExcludeDateChange(RescheduleChangeBase):
    kind: Literal["EXCLUDE_DATE"]
    date: date


class AddTimeWindowChange(RescheduleChangeBase):
    kind: Literal["ADD_TIME_WINDOW"]
    date: date
    start_minute: Annotated[StrictInt, Field(ge=0, le=1439)]
    end_minute: Annotated[StrictInt, Field(ge=1, le=1440)]

    @model_validator(mode="after")
    def validate_interval(self) -> AddTimeWindowChange:
        if self.start_minute >= self.end_minute:
            raise ValueError("A proposed time window must be non-empty.")
        return self


class RemoveTimeWindowChange(RescheduleChangeBase):
    kind: Literal["REMOVE_TIME_WINDOW"]
    date: date
    start_minute: Annotated[StrictInt, Field(ge=0, le=1439)]
    end_minute: Annotated[StrictInt, Field(ge=1, le=1440)]


class SetPersonalAvailabilityChange(RescheduleChangeBase):
    kind: Literal["SET_PERSONAL_AVAILABILITY"]
    participant_id: StrictStr
    date: date
    slots: tuple[AvailabilitySlot, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slot_dates(self) -> SetPersonalAvailabilityChange:
        if any(slot.date != self.date for slot in self.slots):
            raise ValueError("Personal availability slots must match the change date.")
        return self


RescheduleChange = Annotated[
    SetMeetingDatesChange
    | SetStartTimeChange
    | SetEndTimeChange
    | SetDurationChange
    | ExcludeDateChange
    | AddTimeWindowChange
    | RemoveTimeWindowChange
    | SetPersonalAvailabilityChange,
    Field(discriminator="kind"),
]

class RescheduleProposalDraft(DomainModel):
    base_input_revision: Annotated[StrictInt, Field(ge=0)]
    changes: tuple[RescheduleChange, ...] = ()
    ambiguities: tuple[StrictStr, ...] = ()
    summary: StrictStr = Field(min_length=1, max_length=500)


class RescheduleProposal(DomainModel):
    proposal_id: StrictStr
    base_input_revision: Annotated[StrictInt, Field(ge=0)]
    status: ProposalStatus
    changes: tuple[RescheduleChange, ...] = ()
    ambiguities: tuple[StrictStr, ...] = ()
    summary: StrictStr

    @model_validator(mode="after")
    def validate_status(self) -> RescheduleProposal:
        if self.status == ProposalStatus.PROPOSED and (
            self.ambiguities or not self.changes
        ):
            raise ValueError("A proposed change needs changes and no unresolved ambiguity.")
        if self.status == ProposalStatus.CLARIFICATION_REQUIRED and not self.ambiguities:
            raise ValueError("Clarification status requires an ambiguity.")
        if self.status == ProposalStatus.REJECTED and not self.ambiguities:
            raise ValueError("Rejected status must include a rejection reason.")
        return self


class ProposalActor(DomainModel):
    participant_id: StrictStr
    can_edit_own_availability: bool = False


class ProposalValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _meeting_participants(snapshot: MeetingSnapshot):
    return {participant.participant_id: participant for participant in snapshot.participants}


def _active_participant_ids(snapshot: MeetingSnapshot) -> set[str]:
    return {
        participant.participant_id
        for participant in snapshot.participants
        if participant.response_status == ResponseStatus.ACCEPTED
        and participant.eligibility_status == EligibilityStatus.ACTIVE
    }


def _scope(change: RescheduleChange) -> ProposalScope:
    if isinstance(change, SetPersonalAvailabilityChange):
        return ProposalScope.PERSONAL_AVAILABILITY
    return ProposalScope.MEETING_CONSTRAINT


def _authorize_change(
    snapshot: MeetingSnapshot, actor: ProposalActor, change: RescheduleChange
) -> None:
    participants = _meeting_participants(snapshot)
    actor_participant = participants.get(actor.participant_id)
    if (
        actor_participant is None
        or actor_participant.response_status != ResponseStatus.ACCEPTED
        or actor_participant.eligibility_status != EligibilityStatus.ACTIVE
    ):
        raise ProposalValidationError("ACTOR_NOT_ACTIVE", "The acting participant is not active.")

    if _scope(change) == ProposalScope.MEETING_CONSTRAINT:
        if actor_participant.role != ParticipantRole.ORGANIZER:
            raise ProposalValidationError(
                "HOST_REQUIRED", "Only the meeting organizer can change meeting constraints."
            )
        return

    assert isinstance(change, SetPersonalAvailabilityChange)
    if change.participant_id not in participants:
        raise ProposalValidationError(
            "PARTICIPANT_NOT_FOUND", "The referenced participant does not exist in this meeting."
        )
    if change.participant_id != actor.participant_id or not actor.can_edit_own_availability:
        raise ProposalValidationError(
            "AVAILABILITY_PERMISSION_DENIED",
            "A participant may change only their own availability when authorized.",
        )


def validate_proposal(
    snapshot: MeetingSnapshot,
    actor: ProposalActor,
    draft: RescheduleProposalDraft,
    *,
    today: date | None = None,
) -> RescheduleProposal:
    current_date = today or date.today()
    if draft.base_input_revision != snapshot.input_revision:
        raise ProposalValidationError(
            "STALE_INPUT_REVISION", "The proposal was created for an older input revision."
        )
    if not draft.changes and not draft.ambiguities:
        raise ProposalValidationError("EMPTY_PROPOSAL", "The proposal contains no changes.")

    active_ids = _active_participant_ids(snapshot)
    date_set = set(snapshot.dates)
    change_keys: set[tuple[object, ...]] = set()
    selected_dates: set[date] | None = None
    duration = snapshot.duration_minutes
    start_minutes = dict(snapshot.required_start_minutes_by_date)

    for change in draft.changes:
        _authorize_change(snapshot, actor, change)
        if isinstance(change, SetMeetingDatesChange):
            key = (change.kind,)
        elif isinstance(change, SetDurationChange):
            key = (change.kind,)
        elif isinstance(change, (SetStartTimeChange, SetEndTimeChange)):
            key = (change.kind, change.date)
        elif isinstance(change, (AddTimeWindowChange, RemoveTimeWindowChange)):
            key = (
                "TIME_WINDOW",
                change.date,
                change.start_minute,
                change.end_minute,
            )
        elif isinstance(change, ExcludeDateChange):
            key = (change.kind, change.date)
        else:
            assert isinstance(change, SetPersonalAvailabilityChange)
            key = (change.kind, change.participant_id, change.date)
        if key in change_keys:
            raise ProposalValidationError(
                "CONFLICTING_CHANGES", "The proposal contains conflicting duplicate changes."
            )
        change_keys.add(key)

        if isinstance(change, SetMeetingDatesChange):
            if selected_dates is not None or not set(change.dates) <= date_set:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATES",
                    "Changed meeting dates must be selected from the existing authorized date set.",
                )
            if len(change.dates) != len(set(change.dates)):
                raise ProposalValidationError(
                    "INVALID_MEETING_DATES", "Meeting dates must be unique."
                )
            if any(day < current_date for day in change.dates):
                raise ProposalValidationError(
                    "INVALID_MEETING_DATES", "Past meeting dates are not allowed."
                )
            for participant_id in active_ids:
                submission = snapshot.availability_by_participant_id.get(participant_id)
                if submission is None or any(
                    not any(slot.date == day for slot in submission.slots)
                    for day in change.dates
                ):
                    raise ProposalValidationError(
                        "AVAILABILITY_REFRESH_REQUIRED",
                        "Every participant must have submitted availability for each selected date.",
                    )
            selected_dates = set(change.dates)
        elif isinstance(change, (SetStartTimeChange, SetEndTimeChange)):
            if change.date not in date_set or change.date in snapshot.excluded_dates:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "The requested time is not for an active meeting date."
                )
            if change.date < current_date:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "Past meeting dates are not allowed."
                )
            start = (
                change.minute
                if isinstance(change, SetStartTimeChange)
                else change.minute - duration
            )
            if start < 0 or start + duration > 1440:
                raise ProposalValidationError(
                    "INVALID_TIME_RANGE", "The requested time range exceeds the meeting day."
                )
            start_minutes[change.date] = start
        elif isinstance(change, SetDurationChange):
            duration = change.duration_minutes
            if any(start + duration > 1440 for start in start_minutes.values()):
                raise ProposalValidationError(
                    "INVALID_TIME_RANGE", "The duration exceeds the meeting day."
                )
        elif isinstance(change, ExcludeDateChange):
            if change.date not in date_set or change.date in snapshot.excluded_dates:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "The date cannot be excluded from this meeting."
                )
            if change.date < current_date:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "Past meeting dates are not allowed."
                )
        elif isinstance(change, (AddTimeWindowChange, RemoveTimeWindowChange)):
            if change.date not in date_set or change.date in snapshot.excluded_dates:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "The condition date is not active for this meeting."
                )
            if change.date < current_date:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "Past meeting dates are not allowed."
                )
            if isinstance(change, AddTimeWindowChange):
                existing = {
                    (window.date, window.start_minute, window.end_minute)
                    for window in snapshot.absolute_time_windows
                }
                if (change.date, change.start_minute, change.end_minute) in existing:
                    raise ProposalValidationError(
                        "DUPLICATE_CONDITION", "That time-window condition already exists."
                    )
            else:
                existing = {
                    (window.date, window.start_minute, window.end_minute)
                    for window in snapshot.absolute_time_windows
                }
                if (change.date, change.start_minute, change.end_minute) not in existing:
                    raise ProposalValidationError(
                        "CONDITION_NOT_FOUND", "The condition to remove does not exist."
                    )
        elif isinstance(change, SetPersonalAvailabilityChange):
            if change.date not in date_set or change.date in snapshot.excluded_dates:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "Availability must use an active meeting date."
                )
            if change.date < current_date:
                raise ProposalValidationError(
                    "INVALID_MEETING_DATE", "Past availability dates are not allowed."
                )

    if selected_dates is not None and not selected_dates:
        raise ProposalValidationError(
            "INVALID_MEETING_DATES", "At least one meeting date must remain selected."
        )
    final_active_dates = (
        set(snapshot.dates) - set(snapshot.excluded_dates)
        if selected_dates is None
        else set(selected_dates)
    )
    final_active_dates.difference_update(
        change.date
        for change in draft.changes
        if isinstance(change, ExcludeDateChange)
    )
    if not final_active_dates:
        raise ProposalValidationError(
            "INVALID_MEETING_DATES", "At least one active meeting date must remain."
        )
    exact_times = dict(snapshot.required_start_minutes_by_date)
    explicit_duration = next(
        (change.duration_minutes for change in draft.changes if isinstance(change, SetDurationChange)),
        snapshot.duration_minutes,
    )
    for change in draft.changes:
        if isinstance(change, SetStartTimeChange):
            exact_times[change.date] = change.minute
        elif isinstance(change, SetEndTimeChange):
            exact_times[change.date] = change.minute - explicit_duration
    exact_start_changes = {
        change.date: change.minute
        for change in draft.changes
        if isinstance(change, SetStartTimeChange)
    }
    exact_end_changes = {
        change.date: change.minute
        for change in draft.changes
        if isinstance(change, SetEndTimeChange)
    }
    for day in exact_start_changes.keys() & exact_end_changes.keys():
        if exact_start_changes[day] + explicit_duration != exact_end_changes[day]:
            raise ProposalValidationError(
                "CONFLICTING_TIME_CHANGES",
                "The proposed start, end, and duration do not describe one time interval.",
            )
    if any(day not in (selected_dates or date_set) for day in exact_times):
        exact_times = {
            day: minute
            for day, minute in exact_times.items()
            if day in (selected_dates or date_set)
        }
    if any(minute + explicit_duration > 1440 for minute in exact_times.values()):
        raise ProposalValidationError(
            "INVALID_TIME_RANGE", "The proposed time and duration exceed the meeting day."
        )

    status = (
        ProposalStatus.CLARIFICATION_REQUIRED
        if draft.ambiguities
        else ProposalStatus.PROPOSED
    )
    return RescheduleProposal(
        proposal_id=str(uuid4()),
        base_input_revision=draft.base_input_revision,
        status=status,
        changes=draft.changes,
        ambiguities=draft.ambiguities,
        summary=draft.summary,
    )


class LocalProposalApprovalAdapter:
    """Local-only explicit confirmation; no API or durable approval is implied."""

    def approve(
        self,
        snapshot: MeetingSnapshot,
        actor: ProposalActor,
        proposal: RescheduleProposal,
        *,
        today: date | None = None,
    ) -> MeetingSnapshot:
        if proposal.status != ProposalStatus.PROPOSED:
            raise ProposalValidationError(
                "PROPOSAL_NOT_APPROVABLE", "Only an unambiguous proposed change can be approved."
            )
        draft = RescheduleProposalDraft(
            base_input_revision=proposal.base_input_revision,
            changes=proposal.changes,
            ambiguities=proposal.ambiguities,
            summary=proposal.summary,
        )
        validate_proposal(snapshot, actor, draft, today=today)

        payload = snapshot.model_dump(mode="python")
        for change in proposal.changes:
            if isinstance(change, SetMeetingDatesChange):
                payload["excluded_dates"] = tuple(
                    sorted(set(snapshot.dates) - set(change.dates))
                )
            elif isinstance(change, ExcludeDateChange):
                payload["excluded_dates"] = tuple(
                    sorted(set(payload["excluded_dates"]) | {change.date})
                )
            elif isinstance(change, SetDurationChange):
                payload["duration_minutes"] = change.duration_minutes
            elif isinstance(change, SetStartTimeChange):
                payload["required_start_minutes_by_date"][change.date] = change.minute
            elif isinstance(change, SetEndTimeChange):
                duration = next(
                    (
                        item.duration_minutes
                        for item in proposal.changes
                        if isinstance(item, SetDurationChange)
                    ),
                    snapshot.duration_minutes,
                )
                payload["required_start_minutes_by_date"][change.date] = (
                    change.minute - duration
                )
            elif isinstance(change, AddTimeWindowChange):
                payload["absolute_time_windows"] = (
                    *payload["absolute_time_windows"],
                    AbsoluteTimeWindow(
                        date=change.date,
                        start_minute=change.start_minute,
                        end_minute=change.end_minute,
                    ),
                )
            elif isinstance(change, RemoveTimeWindowChange):
                payload["absolute_time_windows"] = tuple(
                    window
                    for window in payload["absolute_time_windows"]
                    if not (
                        window.date == change.date
                        and window.start_minute == change.start_minute
                        and window.end_minute == change.end_minute
                    )
                )
            elif isinstance(change, SetPersonalAvailabilityChange):
                old_submission = payload["availability_by_participant_id"].get(
                    change.participant_id
                )
                existing_slots = (
                    ()
                    if old_submission is None
                    else tuple(
                        slot
                        for slot in old_submission.slots
                        if slot.date != change.date
                    )
                )
                updated_slots = tuple(
                    sorted(
                        (*existing_slots, *change.slots),
                        key=lambda slot: (
                            slot.date,
                            slot.start_minute,
                            slot.end_minute,
                        ),
                    )
                )
                submission_version = (
                    1 if old_submission is None else old_submission.submission_version + 1
                )
                payload["availability_by_participant_id"][change.participant_id] = (
                    AvailabilitySubmission(
                        participant_id=change.participant_id,
                        status=AvailabilityStatus.SUBMITTED,
                        slots=updated_slots,
                        submitted_at=(
                            None if old_submission is None else old_submission.submitted_at
                        ),
                        updated_at=datetime.now(timezone.utc),
                        submission_version=submission_version,
                    )
                )

        updated = MeetingSnapshot.model_validate(payload)
        updated_payload = updated.model_dump(mode="python")
        updated_payload["input_revision"] = snapshot.input_revision + 1
        updated_payload["run_id"] = str(uuid4())
        updated_payload["consent_round"] = snapshot.consent_round + 1
        hash_payload = updated.model_dump(mode="json", exclude={"input_snapshot_hash"})
        hash_payload["input_revision"] = snapshot.input_revision + 1
        hash_payload["run_id"] = updated_payload["run_id"]
        hash_payload["consent_round"] = snapshot.consent_round + 1
        updated_payload["input_snapshot_hash"] = hashlib.sha256(
            json.dumps(
                hash_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return MeetingSnapshot.model_validate(updated_payload)

    def reject(
        self,
        snapshot: MeetingSnapshot,
        proposal: RescheduleProposal,
    ) -> MeetingSnapshot:
        if proposal.status == ProposalStatus.REJECTED:
            raise ProposalValidationError(
                "PROPOSAL_ALREADY_REJECTED", "A rejected proposal cannot be reviewed."
            )
        return snapshot


def parse_proposal_payload(payload: str, *, base_revision: int) -> RescheduleProposalDraft:
    import json

    try:
        decoded = json.loads(payload)
        decoded.setdefault("base_input_revision", base_revision)
        return RescheduleProposalDraft.model_validate(decoded)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ProposalValidationError(
            "INVALID_MODEL_OUTPUT", "The model output was not valid proposal JSON."
        ) from exc


def proposal_scope(change: RescheduleChange) -> ProposalScope:
    return _scope(change)
