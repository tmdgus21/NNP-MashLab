from __future__ import annotations

import hashlib
import json
from datetime import date

from potato_agent.models import (
    AvailabilityStatus,
    Candidate,
    MeetingSnapshot,
    Participant,
    RecommendationType,
    SolverResult,
    SolverStatus,
)


class CandidateValidationError(ValueError):
    pass


class StaleInputRevision(ValueError):
    pass


def _eligible_participants(snapshot: MeetingSnapshot) -> list[Participant]:
    return [
        participant
        for participant in snapshot.participants
        if participant.response_status.value == "ACCEPTED"
        and participant.eligibility_status.value == "ACTIVE"
    ]


def _interval_is_available(
    snapshot: MeetingSnapshot,
    participant_id: str,
    candidate_date: date,
    start: int,
    end: int,
) -> bool:
    submission = snapshot.availability_by_participant_id.get(participant_id)
    if submission is None or submission.status != AvailabilityStatus.SUBMITTED:
        return False
    covered_until = start
    for slot in sorted(
        (slot for slot in submission.slots if slot.date == candidate_date),
        key=lambda item: (item.start_minute, item.end_minute),
    ):
        if slot.start_minute > covered_until:
            break
        covered_until = max(covered_until, slot.end_minute)
        if covered_until >= end:
            return True
    return False


def _candidate_id(
    snapshot: MeetingSnapshot,
    candidate_date: date,
    start: int,
    end: int,
    attendee_ids: tuple[str, ...],
) -> str:
    payload = json.dumps(
        [
            snapshot.meeting_id,
            snapshot.run_id,
            snapshot.input_revision,
            snapshot.input_snapshot_hash,
            candidate_date.isoformat(),
            start,
            end,
            attendee_ids,
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    return "local-" + hashlib.sha256(payload).hexdigest()[:20]


def validate_solver_candidates(
    snapshot: MeetingSnapshot,
    result: SolverResult,
    recommendation_type: RecommendationType,
    all_attendee_status: SolverStatus,
    current_revision: int,
) -> list[Candidate]:
    if current_revision != snapshot.input_revision:
        raise StaleInputRevision("Input revision changed during solve.")
    if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        raise CandidateValidationError("Only feasible solver results can be validated.")
    if not result.candidates:
        raise CandidateValidationError("A feasible result must contain candidates.")
    if recommendation_type == RecommendationType.PARTIAL_ALTERNATIVE:
        if all_attendee_status != SolverStatus.INFEASIBLE:
            raise CandidateValidationError(
                "Partial search requires proven all-attendee infeasibility."
            )
        if result.status == SolverStatus.OPTIMAL and not result.maximum_attendees_proven:
            raise CandidateValidationError(
                "An optimal partial result must prove the maximum attendee count."
            )

    eligible_ids = {p.participant_id for p in _eligible_participants(snapshot)}
    validated: list[Candidate] = []
    for raw in result.candidates:
        if raw.meeting_id != snapshot.meeting_id or raw.agent_run_id != snapshot.run_id:
            raise CandidateValidationError("Candidate meeting or run does not match the snapshot.")
        if raw.source_revision != snapshot.input_revision:
            raise CandidateValidationError("Candidate input revision is stale.")
        if raw.source_snapshot_hash != snapshot.input_snapshot_hash:
            raise CandidateValidationError("Candidate input snapshot hash does not match.")
        if raw.recommendation_type != recommendation_type:
            raise CandidateValidationError("Candidate recommendation type does not match its search.")
        if raw.date not in snapshot.dates:
            raise CandidateValidationError("Candidate date is outside the meeting date range.")
        if raw.date in snapshot.excluded_dates:
            raise CandidateValidationError("Candidate uses an excluded meeting date.")
        required_start = snapshot.required_start_minutes_by_date.get(raw.date)
        if required_start is not None and raw.start_minute != required_start:
            raise CandidateValidationError("Candidate does not match the required start time.")
        if raw.end_minute - raw.start_minute != snapshot.duration_minutes:
            raise CandidateValidationError("Candidate duration does not match the meeting.")

        time_windows = [
            window
            for window in snapshot.absolute_time_windows
            if window.date == raw.date
        ]
        if time_windows and not any(
            raw.start_minute >= window.start_minute
            and raw.end_minute <= window.end_minute
            for window in time_windows
        ):
            raise CandidateValidationError("Candidate violates an absolute time window.")

        attendee_ids = raw.attendee_ids
        unavailable_ids = raw.unavailable_ids
        if len(attendee_ids) != len(set(attendee_ids)):
            raise CandidateValidationError("Candidate attendee IDs must be unique.")
        if len(unavailable_ids) != len(set(unavailable_ids)):
            raise CandidateValidationError("Candidate unavailable IDs must be unique.")
        if set(attendee_ids) & set(unavailable_ids):
            raise CandidateValidationError("Attendees and unavailable participants overlap.")
        if set(attendee_ids) | set(unavailable_ids) != eligible_ids:
            raise CandidateValidationError("Candidate does not partition the eligible roster.")

        if recommendation_type == RecommendationType.ALL_AVAILABLE:
            if set(attendee_ids) != eligible_ids or unavailable_ids:
                raise CandidateValidationError(
                    "All-attendee candidate omits an eligible participant."
                )
        elif len(attendee_ids) < snapshot.minimum_attendee_count:
            raise CandidateValidationError("Partial candidate is below the host-set minimum.")

        for participant_id in attendee_ids:
            if not _interval_is_available(
                snapshot, participant_id, raw.date, raw.start_minute, raw.end_minute
            ):
                raise CandidateValidationError(
                    "Candidate attendee lacks submitted covering availability."
                )
        for participant_id in unavailable_ids:
            if _interval_is_available(
                snapshot, participant_id, raw.date, raw.start_minute, raw.end_minute
            ):
                raise CandidateValidationError(
                    "Candidate marks an available participant unavailable."
                )

        ordered_attendees = tuple(sorted(attendee_ids))
        validated.append(
            Candidate(
                candidate_id=_candidate_id(
                    snapshot,
                    raw.date,
                    raw.start_minute,
                    raw.end_minute,
                    ordered_attendees,
                ),
                meeting_id=snapshot.meeting_id,
                agent_run_id=snapshot.run_id,
                source_revision=snapshot.input_revision,
                source_snapshot_hash=snapshot.input_snapshot_hash,
                date=raw.date,
                start_minute=raw.start_minute,
                end_minute=raw.end_minute,
                time_zone="Asia/Seoul",
                recommendation_type=recommendation_type,
                attendee_ids=ordered_attendees,
                unavailable_ids=tuple(sorted(unavailable_ids)),
                solver_status=result.status,
                maximum_attendees_proven=result.maximum_attendees_proven,
                explanation=(
                    "Verified local CP-SAT result; maximum attendance proven."
                    if result.maximum_attendees_proven
                    else "Verified feasible result; maximum attendance is not proven."
                ),
            )
        )

    unique = {
        (
            candidate.date,
            candidate.start_minute,
            candidate.end_minute,
            candidate.attendee_ids,
        ): candidate
        for candidate in validated
    }
    return sorted(
        unique.values(),
        key=lambda candidate: (
            -len(candidate.attendee_ids),
            candidate.date,
            candidate.start_minute,
            candidate.end_minute,
            candidate.attendee_ids,
        ),
    )[:3]
