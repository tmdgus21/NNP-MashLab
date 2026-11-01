from __future__ import annotations

from typing import Protocol

from potato_agent.models import MeetingSnapshot, SolverResult, SolverStatus


class SolverAdapter(Protocol):
    def load_snapshot(self, meeting_id: str) -> MeetingSnapshot: ...

    def current_input_revision(self, meeting_id: str) -> int: ...

    def solve_all_attendees(self, snapshot: MeetingSnapshot) -> SolverResult: ...

    def solve_partial_attendees(
        self, snapshot: MeetingSnapshot, minimum_attendee_count: int
    ) -> SolverResult: ...


class FixtureToolAdapter:
    """Deterministic local-test adapter; it never invokes an AI or optimizer."""

    def __init__(
        self,
        snapshot: MeetingSnapshot,
        all_result: SolverResult,
        partial_result: SolverResult | None = None,
        *,
        revision_after_all: int | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.all_result = all_result
        self.partial_result = partial_result or SolverResult(status=SolverStatus.NOT_RUN)
        self.current_revision = snapshot.input_revision
        self.revision_after_all = revision_after_all
        self.calls: list[tuple[str, int | None]] = []

    def load_snapshot(self, meeting_id: str) -> MeetingSnapshot:
        if meeting_id != self.snapshot.meeting_id:
            raise ValueError("Fixture adapter received an unknown meeting.")
        self.calls.append(("load_snapshot", None))
        return self.snapshot

    def current_input_revision(self, meeting_id: str) -> int:
        if meeting_id != self.snapshot.meeting_id:
            raise ValueError("Fixture adapter received an unknown meeting.")
        return self.current_revision

    def solve_all_attendees(self, snapshot: MeetingSnapshot) -> SolverResult:
        self.calls.append(("solve_all_attendees", None))
        if self.revision_after_all is not None:
            self.current_revision = self.revision_after_all
        return self.all_result

    def solve_partial_attendees(
        self, snapshot: MeetingSnapshot, minimum_attendee_count: int
    ) -> SolverResult:
        self.calls.append(("solve_partial_attendees", minimum_attendee_count))
        return self.partial_result
