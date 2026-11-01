from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable

from ortools.sat.python import cp_model

from potato_agent.models import (
    AvailabilityStatus,
    MeetingSnapshot,
    Participant,
    RecommendationType,
    ResponseStatus,
    RawCandidate,
    SolverResult,
    SolverStatus,
)


@dataclass(frozen=True)
class _TimeOption:
    date: date
    start_minute: int
    end_minute: int
    attendee_ids: tuple[str, ...]


def _eligible_participants(snapshot: MeetingSnapshot) -> list[Participant]:
    return sorted(
        (
            participant
            for participant in snapshot.participants
            if participant.response_status == ResponseStatus.ACCEPTED
            and participant.eligibility_status.value == "ACTIVE"
        ),
        key=lambda participant: participant.participant_id,
    )


def _validate_ready_snapshot(snapshot: MeetingSnapshot) -> None:
    pending = [
        participant.participant_id
        for participant in snapshot.participants
        if participant.response_status == ResponseStatus.PENDING
        and participant.eligibility_status.value == "ACTIVE"
    ]
    missing = [
        participant.participant_id
        for participant in _eligible_participants(snapshot)
        if (
            participant.participant_id
            not in snapshot.availability_by_participant_id
            or snapshot.availability_by_participant_id[
                participant.participant_id
            ].status
            != AvailabilityStatus.SUBMITTED
        )
    ]
    if pending or missing:
        raise ValueError(
            "Snapshot is not ready: "
            f"pending RSVP IDs={pending}; availability-not-submitted IDs={missing}."
        )
    if len(_eligible_participants(snapshot)) < 2:
        raise ValueError("At least two eligible participants are required.")


def _merged_intervals(snapshot: MeetingSnapshot, participant_id: str) -> dict[date, list[tuple[int, int]]]:
    submission = snapshot.availability_by_participant_id[participant_id]
    grouped: dict[date, list[tuple[int, int]]] = {}
    for slot in submission.slots:
        grouped.setdefault(slot.date, []).append((slot.start_minute, slot.end_minute))

    merged: dict[date, list[tuple[int, int]]] = {}
    for slot_date, intervals in grouped.items():
        combined: list[list[int]] = []
        for start, end in sorted(intervals):
            if combined and start <= combined[-1][1]:
                combined[-1][1] = max(combined[-1][1], end)
            else:
                combined.append([start, end])
        merged[slot_date] = [(start, end) for start, end in combined]
    return merged


def _covered(intervals: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(slot_start <= start and end <= slot_end for slot_start, slot_end in intervals)


def _enumerate_options(
    snapshot: MeetingSnapshot,
    minimum_attendee_count: int,
    recommendation_type: RecommendationType,
    cancellation_event: threading.Event,
) -> list[_TimeOption] | None:
    participants = _eligible_participants(snapshot)
    availability = {
        participant.participant_id: _merged_intervals(
            snapshot, participant.participant_id
        )
        for participant in participants
    }
    windows_by_date: dict[date, list[tuple[int, int]]] = {}
    for window in snapshot.absolute_time_windows:
        windows_by_date.setdefault(window.date, []).append(
            (window.start_minute, window.end_minute)
        )

    options: list[_TimeOption] = []
    latest_start = 1440 - snapshot.duration_minutes
    for meeting_date in sorted(snapshot.dates):
        if cancellation_event.is_set():
            return None
        if meeting_date in snapshot.excluded_dates:
            continue
        windows = windows_by_date.get(meeting_date, [])
        required_start = snapshot.required_start_minutes_by_date.get(meeting_date)
        starts = (
            (required_start,)
            if required_start is not None
            else range(latest_start + 1)
        )
        for start in starts:
            if start % 128 == 0 and cancellation_event.is_set():
                return None
            if start > latest_start:
                continue
            end = start + snapshot.duration_minutes
            if windows and not any(
                window_start <= start and end <= window_end
                for window_start, window_end in windows
            ):
                continue
            attendee_ids = tuple(
                participant.participant_id
                for participant in participants
                if _covered(
                    availability[participant.participant_id].get(meeting_date, []),
                    start,
                    end,
                )
            )
            if recommendation_type == RecommendationType.ALL_AVAILABLE:
                if len(attendee_ids) != len(participants):
                    continue
            elif len(attendee_ids) < minimum_attendee_count:
                continue
            options.append(
                _TimeOption(meeting_date, start, end, attendee_ids)
            )
    return options


def _raw_candidate(
    snapshot: MeetingSnapshot,
    option: _TimeOption,
    recommendation_type: RecommendationType,
    eligible_ids: set[str],
) -> RawCandidate:
    attendees = set(option.attendee_ids)
    return RawCandidate(
        meeting_id=snapshot.meeting_id,
        agent_run_id=snapshot.run_id,
        source_revision=snapshot.input_revision,
        source_snapshot_hash=snapshot.input_snapshot_hash,
        date=option.date,
        start_minute=option.start_minute,
        end_minute=option.end_minute,
        time_zone="Asia/Seoul",
        recommendation_type=recommendation_type,
        attendee_ids=option.attendee_ids,
        unavailable_ids=tuple(sorted(eligible_ids - attendees)),
    )


def _result(
    status: SolverStatus,
    started_at: float,
    candidates: tuple[RawCandidate, ...] = (),
    *,
    maximum_attendees_proven: bool = False,
    diagnostic: str | None = None,
) -> SolverResult:
    return SolverResult(
        status=status,
        candidates=candidates,
        maximum_attendees_proven=maximum_attendees_proven,
        solve_time_seconds=max(0.0, time.monotonic() - started_at),
        diagnostic=diagnostic,
    )


class CpSatSolverAdapter:
    """Local OR-Tools adapter; it reads snapshots and never persists results."""

    def __init__(
        self,
        snapshot: MeetingSnapshot,
        *,
        time_limit_seconds: float = 5.0,
        revision_provider: Callable[[str], int] | None = None,
        cancellation_event: threading.Event | None = None,
    ) -> None:
        if time_limit_seconds <= 0:
            raise ValueError("time_limit_seconds must be greater than zero.")
        self.snapshot = snapshot
        self.time_limit_seconds = time_limit_seconds
        self.revision_provider = revision_provider or (
            lambda meeting_id: snapshot.input_revision
        )
        self.cancellation_event = cancellation_event or threading.Event()

    def load_snapshot(self, meeting_id: str) -> MeetingSnapshot:
        if meeting_id != self.snapshot.meeting_id:
            raise ValueError("Solver adapter received an unknown meeting.")
        return self.snapshot

    def current_input_revision(self, meeting_id: str) -> int:
        if meeting_id != self.snapshot.meeting_id:
            raise ValueError("Solver adapter received an unknown meeting.")
        return self.revision_provider(meeting_id)

    def solve_all_attendees(self, snapshot: MeetingSnapshot) -> SolverResult:
        return self._solve(snapshot, RecommendationType.ALL_AVAILABLE, 0)

    def solve_partial_attendees(
        self, snapshot: MeetingSnapshot, minimum_attendee_count: int
    ) -> SolverResult:
        if minimum_attendee_count != snapshot.minimum_attendee_count:
            return _result(
                SolverStatus.ERROR,
                time.monotonic(),
                diagnostic="Partial minimum must match the host-configured meeting value.",
            )
        return self._solve(
            snapshot,
            RecommendationType.PARTIAL_ALTERNATIVE,
            minimum_attendee_count,
        )

    def _solve(
        self,
        snapshot: MeetingSnapshot,
        recommendation_type: RecommendationType,
        minimum_attendee_count: int,
    ) -> SolverResult:
        started_at = time.monotonic()
        if snapshot.meeting_id != self.snapshot.meeting_id:
            return _result(
                SolverStatus.ERROR,
                started_at,
                diagnostic="Solver adapter received a snapshot for another meeting.",
            )
        try:
            if self.current_input_revision(snapshot.meeting_id) != snapshot.input_revision:
                return _result(
                    SolverStatus.STALE,
                    started_at,
                    diagnostic="Input revision changed before CP-SAT started.",
                )
            _validate_ready_snapshot(snapshot)
        except Exception as exc:
            return _result(
                SolverStatus.ERROR,
                started_at,
                diagnostic=f"{type(exc).__name__}: {exc}",
            )

        if self.cancellation_event.is_set():
            return _result(
                SolverStatus.CANCELLED,
                started_at,
                diagnostic="Cancellation was requested before CP-SAT started.",
            )

        options = _enumerate_options(
            snapshot,
            minimum_attendee_count,
            recommendation_type,
            self.cancellation_event,
        )
        if options is None:
            return _result(
                SolverStatus.CANCELLED,
                started_at,
                diagnostic="Candidate enumeration stopped after cancellation.",
            )
        try:
            current_revision = self.current_input_revision(snapshot.meeting_id)
        except Exception as exc:
            return _result(
                SolverStatus.ERROR,
                started_at,
                diagnostic=f"{type(exc).__name__}: {exc}",
            )
        if current_revision != snapshot.input_revision:
            return _result(
                SolverStatus.STALE,
                started_at,
                diagnostic="Input revision changed during candidate enumeration.",
            )
        if not options:
            return _result(SolverStatus.INFEASIBLE, started_at)

        model = cp_model.CpModel()
        selected = [
            model.new_bool_var(f"slot_{index}")
            for index in range(len(options))
        ]
        model.add_exactly_one(selected)
        if recommendation_type == RecommendationType.PARTIAL_ALTERNATIVE:
            model.maximize(
                sum(
                    len(option.attendee_ids) * selected[index]
                    for index, option in enumerate(options)
                )
            )
        else:
            model.minimize(
                sum(index * variable for index, variable in enumerate(selected))
            )

        model_error = model.validate()
        if model_error:
            return _result(
                SolverStatus.MODEL_INVALID,
                started_at,
                diagnostic=model_error,
            )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0

        monitor_done = threading.Event()
        monitor: threading.Thread | None = None
        if self.cancellation_event is not None:
            def stop_when_cancelled() -> None:
                while not monitor_done.wait(0.01):
                    if self.cancellation_event.is_set():
                        solver.stop_search()
                        return

            monitor = threading.Thread(target=stop_when_cancelled, daemon=True)
            monitor.start()

        try:
            cp_status = solver.solve(model)
        except Exception as exc:
            return _result(
                SolverStatus.ERROR,
                started_at,
                diagnostic=f"{type(exc).__name__}: {exc}",
            )
        finally:
            monitor_done.set()
            if monitor is not None:
                monitor.join(timeout=1.0)

        if self.cancellation_event.is_set():
            return _result(
                SolverStatus.CANCELLED,
                started_at,
                diagnostic="CP-SAT stopped after a cancellation request.",
            )
        try:
            current_revision = self.current_input_revision(snapshot.meeting_id)
        except Exception as exc:
            return _result(
                SolverStatus.ERROR,
                started_at,
                diagnostic=f"{type(exc).__name__}: {exc}",
            )
        if current_revision != snapshot.input_revision:
            return _result(
                SolverStatus.STALE,
                started_at,
                diagnostic="Input revision changed while CP-SAT was running.",
            )

        status_map = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
            cp_model.UNKNOWN: SolverStatus.UNKNOWN,
        }
        status = status_map.get(cp_status, SolverStatus.ERROR)
        solve_time = solver.wall_time
        if (
            status == SolverStatus.UNKNOWN
            and solve_time >= self.time_limit_seconds * 0.9
        ):
            status = SolverStatus.TIMEOUT

        if status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            return _result(
                status,
                started_at,
                diagnostic=solver.status_name(cp_status),
            )

        eligible_ids = {
            participant.participant_id
            for participant in _eligible_participants(snapshot)
        }
        if recommendation_type == RecommendationType.PARTIAL_ALTERNATIVE:
            chosen_index = next(
                index for index, variable in enumerate(selected) if solver.value(variable)
            )
            attendee_count = len(options[chosen_index].attendee_ids)
            if status == SolverStatus.OPTIMAL:
                chosen_options = [
                    option
                    for option in options
                    if len(option.attendee_ids) == attendee_count
                ][:3]
            else:
                chosen_options = [options[chosen_index]]
            maximum_proven = status == SolverStatus.OPTIMAL
        else:
            chosen_options = options[:3]
            maximum_proven = True

        candidates = tuple(
            _raw_candidate(
                snapshot,
                option,
                recommendation_type,
                eligible_ids,
            )
            for option in chosen_options
        )
        return _result(
            status,
            started_at,
            candidates,
            maximum_attendees_proven=maximum_proven,
        )
