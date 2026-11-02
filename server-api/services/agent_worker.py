"""Lease-based Agent Run execution and atomic candidate persistence."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.agent import AgentCandidate, AgentCandidateMember, AgentRun
from db_v21.models.room import Room, RoomMember
from potato_agent.models import (
    AgentStatus,
    Candidate,
    EligibilityStatus,
    ParticipantRole,
    RecommendationType,
    ResponseStatus,
)
from services.agent_run import AgentRunResult
from services.agent_solver import (
    AgentCandidateValidationError,
    AgentSolverCancelledError,
    AgentSolverOutput,
    AgentSolverServiceError,
    AgentSolverTimeoutError,
    AgentSolverUnknownError,
    StaleAgentRunError,
    run_agent_solver,
)
from services.meeting_snapshot import (
    MeetingSnapshot,
    RoomNotFoundError,
    SnapshotBuildError,
    build_meeting_snapshot,
)


SessionFactory = Callable[[], Session]
SEOUL = ZoneInfo("Asia/Seoul")


class AgentWorkerError(Exception):
    code = "AGENT_WORKER_ERROR"


class WorkerLeaseLostError(AgentWorkerError):
    code = "WORKER_LEASE_LOST"


class AgentRunNotFoundError(AgentWorkerError):
    code = "AGENT_RUN_NOT_FOUND"


class AgentWorkerConfigurationError(AgentWorkerError):
    code = "INVALID_WORKER_CONFIGURATION"


@dataclass(frozen=True)
class AgentRunClaim:
    run: AgentRunResult
    worker_id: str
    lease_token: str = field(repr=False)
    lease_expires_at: datetime


@dataclass(frozen=True)
class PersistedAgentCandidate:
    id: str
    rank: int
    candidate: Candidate


@dataclass(frozen=True)
class AgentWorkerResult:
    run_id: str
    status: str
    attempt_number: int
    candidates: tuple[PersistedAgentCandidate, ...] = ()
    error_code: str | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _snapshot_for_run(run: AgentRun) -> MeetingSnapshot:
    snapshot = MeetingSnapshot.model_validate(run.input_snapshot)
    if (
        snapshot.meeting_id != run.room_id
        or snapshot.run_id != run.id
        or snapshot.agent_session_id != run.agent_session_id
        or snapshot.input_revision != run.source_revision
        or snapshot.input_snapshot_hash != run.input_snapshot_hash
        or snapshot.consent_round != run.consent_round
    ):
        raise AgentWorkerError("Persisted run metadata does not match its snapshot.")
    return snapshot


def _run_result(db: Session, row: AgentRun) -> AgentRunResult:
    snapshot = _snapshot_for_run(row)
    creator = (
        db.get(RoomMember, row.created_by_member_id)
        if row.created_by_member_id is not None
        else None
    )
    return AgentRunResult(
        run_id=row.id,
        agent_session_id=row.agent_session_id,
        meeting_id=row.room_id,
        status=row.status,
        source_revision=row.source_revision,
        input_snapshot_hash=row.input_snapshot_hash,
        created_by_account_id=creator.account_id if creator else "",
        created_by_member_id=row.created_by_member_id or "",
        snapshot=snapshot,
        replayed=False,
    )


def _clear_lease(row: AgentRun) -> None:
    row.worker_id = None
    row.lease_token_hash = None
    row.lease_expires_at = None
    row.heartbeat_at = None


def claim_next_agent_run(
    session_factory: SessionFactory,
    *,
    worker_id: str,
    lease_seconds: int = 60,
    max_attempts: int = 3,
) -> AgentRunClaim | None:
    """Atomically claim queued work or reclaim a run with an expired lease."""
    if not worker_id or len(worker_id) > 128:
        raise AgentWorkerConfigurationError("worker_id must be 1..128 characters.")
    if lease_seconds < 3 or max_attempts < 1:
        raise AgentWorkerConfigurationError(
            "lease_seconds must be at least 3 and max_attempts at least 1."
        )

    with session_factory() as db:
        with db.begin():
            rows = list(
                db.scalars(
                    select(AgentRun)
                    .where(
                        or_(
                            AgentRun.status == "QUEUED",
                            AgentRun.status == "RUNNING",
                        )
                    )
                    .order_by(AgentRun.created_at, AgentRun.id)
                    .with_for_update(skip_locked=True)
                )
            )
            current_time = now()
            for row in rows:
                was_expired = (
                    row.status == "RUNNING"
                    and row.lease_expires_at is not None
                    and _utc(row.lease_expires_at) <= current_time
                )
                if row.status == "RUNNING" and not was_expired:
                    continue
                if row.cancel_requested_at is not None:
                    row.status = "CANCELLED"
                    row.completed_at = current_time
                    _clear_lease(row)
                    continue
                if was_expired and row.attempt_number >= max_attempts:
                    row.status = "FAILED"
                    row.error_code = "WORKER_LEASE_EXHAUSTED"
                    row.error_detail = "Worker lease expired at the retry limit."
                    row.completed_at = current_time
                    _clear_lease(row)
                    continue

                token = secrets.token_urlsafe(32)
                row.status = "RUNNING"
                row.worker_id = worker_id
                row.lease_token_hash = _token_digest(token)
                row.lease_expires_at = current_time + timedelta(
                    seconds=lease_seconds
                )
                row.heartbeat_at = current_time
                row.started_at = row.started_at or current_time
                row.completed_at = None
                row.error_code = None
                row.error_detail = None
                if was_expired:
                    row.attempt_number += 1
                    row.checkpoint_thread_id = None
                    row.checkpoint_ref = None
                db.flush()
                try:
                    run_result = _run_result(db, row)
                except (AgentWorkerError, ValueError) as exc:
                    row.status = "FAILED"
                    row.error_code = "SNAPSHOT_INVALID"
                    row.error_detail = f"{type(exc).__name__}: {exc}"
                    row.completed_at = current_time
                    _clear_lease(row)
                    continue
                return AgentRunClaim(
                    run=run_result,
                    worker_id=worker_id,
                    lease_token=token,
                    lease_expires_at=_utc(row.lease_expires_at),
                )
    return None


def request_agent_run_cancel(
    session_factory: SessionFactory, *, run_id: str
) -> bool:
    """Cancel queued work immediately or mark running work for cooperative stop."""
    with session_factory() as db:
        with db.begin():
            return request_agent_run_cancel_in_session(db, run_id=run_id)


def request_agent_run_cancel_in_session(db: Session, *, run_id: str) -> bool:
    """Apply cancellation within the caller's transaction."""
    row = db.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise AgentRunNotFoundError("Agent Run does not exist.")
    if row.status == "QUEUED":
        row.status = "CANCELLED"
        row.cancel_requested_at = now()
        row.completed_at = now()
        row.error_code = None
        row.error_detail = None
        _clear_lease(row)
        return True
    if row.status == "RUNNING":
        row.cancel_requested_at = row.cancel_requested_at or now()
        return True
    return False


def retry_failed_agent_run(
    session_factory: SessionFactory, *, run_id: str
) -> bool:
    """Requeue only retryable failed solver outcomes, retaining immutable input."""
    with session_factory() as db:
        with db.begin():
            row = db.scalar(
                select(AgentRun)
                .where(AgentRun.id == run_id)
                .with_for_update()
            )
            if row is None:
                raise AgentRunNotFoundError("Agent Run does not exist.")
            if row.status != "FAILED" or row.error_code not in {
                "SOLVER_TIMEOUT",
                "SOLVER_UNKNOWN",
                "SOLVER_ERROR",
                "SNAPSHOT_REVALIDATION_FAILED",
                "SOLVER_FAILURE",
                "SOLVER_INTERNAL_ERROR",
            }:
                return False
            if row.attempt_number >= 3:
                return False
            if db.scalar(
                select(AgentCandidate.id)
                .where(AgentCandidate.run_id == row.id)
                .limit(1)
            ):
                return False
            row.status = "QUEUED"
            row.attempt_number += 1
            row.error_code = None
            row.error_detail = None
            row.started_at = None
            row.completed_at = None
            row.cancel_requested_at = None
            row.checkpoint_thread_id = None
            row.checkpoint_ref = None
            _clear_lease(row)
            return True


def _assert_lease(
    row: AgentRun,
    *,
    worker_id: str,
    lease_token: str,
    at: datetime,
) -> None:
    if (
        row.status != "RUNNING"
        or row.worker_id != worker_id
        or row.lease_token_hash is None
        or not hmac.compare_digest(row.lease_token_hash, _token_digest(lease_token))
        or row.lease_expires_at is None
        or _utc(row.lease_expires_at) <= at
    ):
        raise WorkerLeaseLostError("Worker no longer owns a valid Run lease.")


class _LeaseKeeper:
    def __init__(
        self,
        claim: AgentRunClaim,
        session_factory: SessionFactory,
        *,
        lease_seconds: int,
        interval_seconds: float,
    ) -> None:
        self.claim = claim
        self.session_factory = session_factory
        self.lease_seconds = lease_seconds
        self.interval_seconds = interval_seconds
        self.cancelled = threading.Event()
        self.lost = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._keep_lease,
            name=f"agent-lease-{claim.run.run_id}",
            daemon=True,
        )
        self.error: Exception | None = None

    def __enter__(self) -> _LeaseKeeper:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()

    def _keep_lease(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                with self.session_factory() as db:
                    with db.begin():
                        row = db.scalar(
                            select(AgentRun)
                            .where(AgentRun.id == self.claim.run.run_id)
                            .with_for_update()
                        )
                        if row is None:
                            raise WorkerLeaseLostError("Agent Run was removed.")
                        current_time = now()
                        _assert_lease(
                            row,
                            worker_id=self.claim.worker_id,
                            lease_token=self.claim.lease_token,
                            at=current_time,
                        )
                        if row.cancel_requested_at is not None:
                            self.cancelled.set()
                            return
                        row.heartbeat_at = current_time
                        row.lease_expires_at = current_time + timedelta(
                            seconds=self.lease_seconds
                        )
            except Exception as exc:
                self.error = exc
                self.lost.set()
                self.cancelled.set()
                return


def _eligible_participant_ids(snapshot: MeetingSnapshot) -> set[str]:
    return {
        participant.participant_id
        for participant in snapshot.participants
        if participant.role == ParticipantRole.ORGANIZER
        or (
            participant.response_status == ResponseStatus.ACCEPTED
            and participant.eligibility_status == EligibilityStatus.ACTIVE
        )
    }


def _candidate_start_end(candidate: Candidate) -> tuple[datetime, datetime]:
    if not 0 <= candidate.start_minute < 1440:
        raise AgentCandidateValidationError("Candidate start minute is invalid.")
    if not 0 < candidate.end_minute <= 1440:
        raise AgentCandidateValidationError("Candidate end minute is invalid.")
    starts_at = datetime.combine(
        candidate.date,
        time(candidate.start_minute // 60, candidate.start_minute % 60),
        tzinfo=SEOUL,
    )
    ends_at = (
        datetime.combine(candidate.date + timedelta(days=1), time.min, tzinfo=SEOUL)
        if candidate.end_minute == 1440
        else datetime.combine(
            candidate.date,
            time(candidate.end_minute // 60, candidate.end_minute % 60),
            tzinfo=SEOUL,
        )
    )
    if ends_at <= starts_at:
        raise AgentCandidateValidationError("Candidate interval is not positive.")
    return starts_at, ends_at


def _validate_candidates(
    snapshot: MeetingSnapshot, output: AgentSolverOutput
) -> tuple[Candidate, ...]:
    candidates = output.candidates
    if len(candidates) > 3:
        raise AgentCandidateValidationError("Agent Core returned more than TOP 3.")
    if output.status not in (
        AgentStatus.ALL_AVAILABLE,
        AgentStatus.PARTIAL_ALTERNATIVE,
    ):
        if candidates:
            raise AgentCandidateValidationError(
                "Non-candidate Agent status returned candidates."
            )
        return ()
    if not candidates:
        raise AgentCandidateValidationError("Candidate status requires candidates.")

    eligible_ids = _eligible_participant_ids(snapshot)
    signatures: set[tuple[date, int, int, tuple[str, ...]]] = set()
    ordered = tuple(
        sorted(
            candidates,
            key=lambda item: (
                -len(item.attendee_ids),
                item.date,
                item.start_minute,
                item.end_minute,
                item.attendee_ids,
            ),
        )
    )
    for candidate in ordered:
        if (
            not candidate.verified
            or candidate.meeting_id != snapshot.meeting_id
            or candidate.agent_run_id != snapshot.run_id
            or candidate.source_revision != snapshot.input_revision
            or candidate.source_snapshot_hash != snapshot.input_snapshot_hash
            or candidate.time_zone != "Asia/Seoul"
            or candidate.date not in snapshot.dates
            or candidate.date in snapshot.excluded_dates
            or candidate.end_minute - candidate.start_minute
            != snapshot.duration_minutes
        ):
            raise AgentCandidateValidationError(
                "Candidate metadata or configured meeting interval is invalid."
            )
        required_start = snapshot.required_start_minutes_by_date.get(candidate.date)
        if required_start is not None and candidate.start_minute != required_start:
            raise AgentCandidateValidationError(
                "Candidate does not match the host-configured start time."
            )
        windows = [
            item
            for item in snapshot.absolute_time_windows
            if item.date == candidate.date
        ]
        if windows and not any(
            candidate.start_minute >= item.start_minute
            and candidate.end_minute <= item.end_minute
            for item in windows
        ):
            raise AgentCandidateValidationError(
                "Candidate is outside configured time windows."
            )
        attendees = set(candidate.attendee_ids)
        unavailable = set(candidate.unavailable_ids)
        if (
            len(attendees) != len(candidate.attendee_ids)
            or len(unavailable) != len(candidate.unavailable_ids)
            or attendees & unavailable
            or attendees | unavailable != eligible_ids
        ):
            raise AgentCandidateValidationError(
                "Candidate participant sets do not partition eligible attendees."
            )
        signature = (
            candidate.date,
            candidate.start_minute,
            candidate.end_minute,
            tuple(sorted(attendees)),
        )
        if signature in signatures:
            raise AgentCandidateValidationError("Duplicate Agent candidates returned.")
        signatures.add(signature)

        if output.status == AgentStatus.ALL_AVAILABLE:
            if (
                candidate.recommendation_type != RecommendationType.ALL_AVAILABLE
                or attendees != eligible_ids
                or unavailable
            ):
                raise AgentCandidateValidationError(
                    "All-attendee candidate omits an eligible attendee."
                )
        else:
            if (
                candidate.recommendation_type
                != RecommendationType.PARTIAL_ALTERNATIVE
                or output.all_solver_status is None
                or output.all_solver_status.value != "INFEASIBLE"
                or len(attendees) < snapshot.minimum_attendee_count
            ):
                raise AgentCandidateValidationError(
                    "Partial candidate lacks proven infeasibility or host minimum."
                )
        _candidate_start_end(candidate)
    return ordered


def _store_candidates(
    db: Session,
    *,
    run: AgentRun,
    snapshot: MeetingSnapshot,
    candidates: tuple[Candidate, ...],
) -> tuple[PersistedAgentCandidate, ...]:
    if db.scalar(
        select(AgentCandidate.id).where(AgentCandidate.run_id == run.id).limit(1)
    ):
        raise AgentCandidateValidationError(
            "Candidates already exist for this Run; refusing to overwrite history."
        )

    participant_ids = _eligible_participant_ids(snapshot)
    members = list(
        db.scalars(
            select(RoomMember).where(
                RoomMember.room_id == run.room_id,
                RoomMember.membership_status == "ACTIVE",
                RoomMember.account_id.in_(participant_ids),
            )
        )
    )
    member_by_account = {member.account_id: member for member in members}
    if set(member_by_account) != participant_ids or len(members) != len(participant_ids):
        raise AgentCandidateValidationError(
            "Every eligible Agent participant must resolve to one active room member."
        )

    persisted: list[PersistedAgentCandidate] = []
    for rank, candidate in enumerate(candidates, start=1):
        starts_at, ends_at = _candidate_start_end(candidate)
        candidate_id = str(uuid4())
        db.add(
            AgentCandidate(
                id=candidate_id,
                run_id=run.id,
                rank=rank,
                source_revision=candidate.source_revision,
                source_snapshot_hash=candidate.source_snapshot_hash,
                meeting_date=candidate.date,
                starts_at=starts_at,
                ends_at=ends_at,
                time_zone=candidate.time_zone,
                candidate_type=candidate.recommendation_type.value,
                solver_status=candidate.solver_status.value,
                maximum_attendees_proven=candidate.maximum_attendees_proven,
                verified=True,
                explanation=candidate.explanation,
            )
        )
        for participant_id in sorted(participant_ids):
            attending = participant_id in candidate.attendee_ids
            db.add(
                AgentCandidateMember(
                    candidate_id=candidate_id,
                    room_member_id=member_by_account[participant_id].id,
                    consent_round=run.consent_round,
                    participation_status="ATTENDING" if attending else "UNAVAILABLE",
                    consent_status=None,
                    consented_at=None,
                    consent_note=None,
                )
            )
        persisted.append(
            PersistedAgentCandidate(
                id=candidate_id,
                rank=rank,
                candidate=candidate.model_copy(
                    update={"candidate_id": candidate_id}
                ),
            )
        )
    return tuple(persisted)


def _verify_current_snapshot(db: Session, run: AgentRun) -> MeetingSnapshot:
    room = db.scalar(
        select(Room)
        .where(Room.id == run.room_id, Room.deleted_at.is_(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if room is None:
        raise StaleAgentRunError(
            "The meeting no longer matches the persisted Agent snapshot."
        )
    try:
        current = build_meeting_snapshot(
            db,
            room_id=run.room_id,
            agent_session_id=run.agent_session_id,
            run_id=run.id,
            consent_round=run.consent_round,
        )
    except (RoomNotFoundError, SnapshotBuildError) as exc:
        raise StaleAgentRunError(
            "The meeting no longer matches the persisted Agent snapshot."
        ) from exc
    if (
        current.input_revision != run.source_revision
        or current.input_snapshot_hash != run.input_snapshot_hash
    ):
        raise StaleAgentRunError(
            "Meeting revision or snapshot hash changed before candidate persistence."
        )
    return current


def _finish(
    session_factory: SessionFactory,
    claim: AgentRunClaim,
    *,
    status: str,
    error_code: str | None = None,
    error_detail: str | None = None,
    output: AgentSolverOutput | None = None,
) -> AgentWorkerResult:
    with session_factory() as db:
        with db.begin():
            row = db.scalar(
                select(AgentRun)
                .where(AgentRun.id == claim.run.run_id)
                .with_for_update()
            )
            if row is None:
                raise WorkerLeaseLostError("Agent Run was removed before completion.")
            _assert_lease(
                row,
                worker_id=claim.worker_id,
                lease_token=claim.lease_token,
                at=now(),
            )
            if row.cancel_requested_at is not None:
                status = "CANCELLED"
                output = None
                error_code = None
                error_detail = None
            persisted: tuple[PersistedAgentCandidate, ...] = ()
            if output is not None and status in (
                AgentStatus.ALL_AVAILABLE.value,
                AgentStatus.PARTIAL_ALTERNATIVE.value,
            ):
                snapshot = _verify_current_snapshot(db, row)
                validated = _validate_candidates(snapshot, output)
                persisted = _store_candidates(
                    db,
                    run=row,
                    snapshot=snapshot,
                    candidates=validated,
                )
            elif output is not None:
                _verify_current_snapshot(db, row)

            row.status = status
            row.error_code = error_code
            row.error_detail = error_detail
            row.completed_at = now()
            _clear_lease(row)
            db.flush()
            return AgentWorkerResult(
                run_id=row.id,
                status=row.status,
                attempt_number=row.attempt_number,
                candidates=persisted,
                error_code=row.error_code,
            )


def _terminalize_worker_error(
    session_factory: SessionFactory,
    claim: AgentRunClaim,
    *,
    status: str,
    error_code: str | None,
    error_detail: str | None = None,
) -> AgentWorkerResult:
    try:
        return _finish(
            session_factory,
            claim,
            status=status,
            error_code=error_code,
            error_detail=error_detail,
        )
    except (WorkerLeaseLostError, AgentRunNotFoundError):
        raise


def _execute_solver(
    claim: AgentRunClaim,
    session_factory: SessionFactory,
    *,
    time_limit_seconds: float,
    cancellation_event: threading.Event,
) -> AgentSolverOutput:
    return run_agent_solver(
        claim.run,
        session_factory=session_factory,
        time_limit_seconds=time_limit_seconds,
        cancellation_event=cancellation_event,
        expected_status="RUNNING",
    )


def execute_agent_run(
    claim: AgentRunClaim,
    session_factory: SessionFactory,
    *,
    lease_seconds: int = 60,
    heartbeat_interval_seconds: float | None = None,
    time_limit_seconds: float = 5.0,
) -> AgentWorkerResult:
    """Run a claimed task outside DB transactions and persist its result atomically."""
    if lease_seconds < 3 or time_limit_seconds <= 0:
        raise AgentWorkerConfigurationError("Invalid lease or solver time limit.")
    interval = (
        heartbeat_interval_seconds
        if heartbeat_interval_seconds is not None
        else max(0.1, lease_seconds / 3)
    )
    if interval <= 0 or interval >= lease_seconds:
        raise AgentWorkerConfigurationError(
            "Heartbeat interval must be positive and shorter than the lease."
        )

    with _LeaseKeeper(
        claim,
        session_factory,
        lease_seconds=lease_seconds,
        interval_seconds=interval,
    ) as keeper:
        try:
            output = _execute_solver(
                claim,
                session_factory,
                time_limit_seconds=time_limit_seconds,
                cancellation_event=keeper.cancelled,
            )
        except StaleAgentRunError as exc:
            if keeper.lost.is_set():
                raise WorkerLeaseLostError(
                    "Worker lease was lost while solving."
                ) from keeper.error or exc
            return _terminalize_worker_error(
                session_factory,
                claim,
                status="STALE",
                error_code=exc.code,
                error_detail=str(exc),
            )
        except AgentSolverCancelledError as exc:
            if keeper.lost.is_set():
                raise WorkerLeaseLostError(
                    "Worker lease was lost while solving."
                ) from keeper.error or exc
            return _terminalize_worker_error(
                session_factory,
                claim,
                status="CANCELLED",
                error_code=exc.code,
                error_detail=str(exc),
            )
        except (AgentSolverTimeoutError, AgentSolverUnknownError) as exc:
            if keeper.lost.is_set():
                raise WorkerLeaseLostError(
                    "Worker lease was lost while solving."
                ) from keeper.error or exc
            return _terminalize_worker_error(
                session_factory,
                claim,
                status="FAILED",
                error_code=exc.code,
                error_detail=str(exc),
            )
        except AgentSolverServiceError as exc:
            if keeper.lost.is_set():
                raise WorkerLeaseLostError(
                    "Worker lease was lost while solving."
                ) from keeper.error or exc
            return _terminalize_worker_error(
                session_factory,
                claim,
                status="FAILED",
                error_code=exc.code,
                error_detail=str(exc),
            )
        except Exception as exc:
            if keeper.lost.is_set():
                raise WorkerLeaseLostError(
                    "Worker lease was lost while solving."
                ) from keeper.error or exc
            _terminalize_worker_error(
                session_factory,
                claim,
                status="FAILED",
                error_code="SOLVER_INTERNAL_ERROR",
                error_detail=f"{type(exc).__name__}: {exc}",
            )
            raise

    if keeper.lost.is_set():
        raise WorkerLeaseLostError("Worker lease was lost while solving.") from keeper.error
    try:
        return _finish(
            session_factory,
            claim,
            status=output.status.value,
            output=output,
        )
    except StaleAgentRunError as exc:
        return _terminalize_worker_error(
            session_factory,
            claim,
            status="STALE",
            error_code=exc.code,
            error_detail=str(exc),
        )
    except AgentCandidateValidationError as exc:
        return _terminalize_worker_error(
            session_factory,
            claim,
            status="FAILED",
            error_code=exc.code,
            error_detail=str(exc),
        )
    except Exception as exc:
        _terminalize_worker_error(
            session_factory,
            claim,
            status="FAILED",
            error_code="CANDIDATE_PERSISTENCE_FAILED",
            error_detail=f"{type(exc).__name__}: {exc}",
        )
        raise
