"""Authenticated HTTP endpoints for queued Agent runs."""
import os
from datetime import datetime
from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db_v21.models.agent import AgentCandidate, AgentCandidateMember, AgentRun
from db_v21.models.room import RoomMember
from database import session as open_session
from services import agent_decision, coordination_round
from services.agent_solver import AgentSnapshotRevalidationError
from services.meeting_snapshot import SnapshotBuildError
from services.agent_run import (
    AgentRunServiceError,
    RoomActor,
    StartAgentRunRequest,
    authorize_room_member,
    start_agent_run,
)
from services.agent_worker import (
    AgentRunNotFoundError,
    request_agent_run_cancel_in_session,
)
from user_auth import account_from_authorization, db_session


router = APIRouter(prefix="/v2/rooms/{room_id}/agent-runs", tags=["Agent runs"])


_WORKER_DISPATCH_VALUES = {"NOT_CONFIGURED", "DB_POLLING"}


def _worker_dispatch() -> str:
    """Configured dispatch mode only; worker liveness is never verified here.

    DB_POLLING means a separate worker is expected to poll the queue.
    """
    value = os.getenv("AGENT_WORKER_DISPATCH", "NOT_CONFIGURED").strip().upper()
    return value if value in _WORKER_DISPATCH_VALUES else "NOT_CONFIGURED"


class AgentRunAccepted(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    status: str
    status_url: str = Field(alias="statusUrl")
    candidates_url: str = Field(alias="candidatesUrl")
    replayed: bool
    worker_dispatch: str = Field(alias="workerDispatch")


class AgentRunStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    status: str
    input_revision: int = Field(alias="inputRevision")
    input_snapshot_hash: str = Field(alias="inputSnapshotHash")
    error_code: str | None = Field(alias="errorCode")
    cancel_requested: bool = Field(alias="cancelRequested")
    created_at: datetime = Field(alias="createdAt")
    started_at: datetime | None = Field(alias="startedAt")
    completed_at: datetime | None = Field(alias="completedAt")


class AgentCandidateMemberDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    room_member_id: str = Field(alias="roomMemberId")
    participation_status: str = Field(alias="participationStatus")
    consent_round: int = Field(alias="consentRound")
    consent_status: str | None = Field(alias="consentStatus")
    consented_at: datetime | None = Field(alias="consentedAt")


class AgentCandidateDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str = Field(alias="candidateId")
    rank: int
    source_revision: int = Field(alias="sourceRevision")
    source_snapshot_hash: str = Field(alias="sourceSnapshotHash")
    starts_at: datetime = Field(alias="startsAt")
    ends_at: datetime = Field(alias="endsAt")
    time_zone: str = Field(alias="timeZone")
    candidate_type: str = Field(alias="candidateType")
    solver_status: str = Field(alias="solverStatus")
    maximum_attendees_proven: bool = Field(alias="maximumAttendeesProven")
    verified: bool
    members: list[AgentCandidateMemberDto]


class AgentCandidateList(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    status: str
    candidates: list[AgentCandidateDto]


class AgentRunCancellation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    status: str
    cancel_requested: bool = Field(alias="cancelRequested")


def _raise_service_error(exc: AgentRunServiceError) -> NoReturn:
    detail: dict[str, object] = {"code": exc.code}
    if exc.code == "INPUT_REVISION_CONFLICT":
        detail.update(
            expectedRevision=exc.expected_revision,
            currentRevision=exc.current_revision,
        )
    raise HTTPException(status_code=exc.status_code, detail=detail) from exc


def _authorized_member(
    db: Session, *, room_id: str, authorization: str | None
) -> RoomActor:
    account = account_from_authorization(db, authorization)
    try:
        return authorize_room_member(
            db, room_id=room_id, actor_account_id=account.id
        )
    except AgentRunServiceError as exc:
        _raise_service_error(exc)


def _load_run(db: Session, *, room_id: str, run_id: str) -> AgentRun:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.room_id == room_id,
        )
    )
    if run is None:
        raise HTTPException(
            status_code=404, detail={"code": "AGENT_RUN_NOT_FOUND"}
        )
    return run


@router.post("", status_code=202, response_model=AgentRunAccepted)
def create_agent_run(
    room_id: str,
    body: StartAgentRunRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session, scope="function"),
) -> AgentRunAccepted:
    account = account_from_authorization(db, authorization)
    try:
        result = start_agent_run(
            db,
            room_id=room_id,
            actor_account_id=account.id,
            idempotency_key=idempotency_key,
            request=body,
        )
    except AgentRunServiceError as exc:
        _raise_service_error(exc)
    except SnapshotBuildError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_MEETING_SNAPSHOT"}
        ) from exc

    status_url = f"{request.url.path}/{result.run_id}"
    return AgentRunAccepted(
        runId=result.run_id,
        status=result.status,
        statusUrl=status_url,
        candidatesUrl=f"{status_url}/candidates",
        replayed=result.replayed,
        workerDispatch=_worker_dispatch(),
    )


@router.get("/{run_id}", response_model=AgentRunStatus)
def get_agent_run(
    room_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session, scope="function"),
) -> AgentRunStatus:
    _authorized_member(db, room_id=room_id, authorization=authorization)
    run = _load_run(db, room_id=room_id, run_id=run_id)
    return AgentRunStatus(
        runId=run.id,
        status=run.status,
        inputRevision=run.source_revision,
        inputSnapshotHash=run.input_snapshot_hash,
        errorCode=run.error_code,
        cancelRequested=run.cancel_requested_at is not None,
        createdAt=run.created_at,
        startedAt=run.started_at,
        completedAt=run.completed_at,
    )


@router.get("/{run_id}/candidates", response_model=AgentCandidateList)
def list_agent_run_candidates(
    room_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session, scope="function"),
) -> AgentCandidateList:
    _authorized_member(db, room_id=room_id, authorization=authorization)
    run = _load_run(db, room_id=room_id, run_id=run_id)
    candidates = list(
        db.scalars(
            select(AgentCandidate)
            .where(AgentCandidate.run_id == run.id)
            .order_by(AgentCandidate.rank)
        )
    )
    candidate_dtos = []
    for candidate in candidates:
        members = db.execute(
            select(AgentCandidateMember)
            .join(
                RoomMember,
                RoomMember.id == AgentCandidateMember.room_member_id,
            )
            .where(
                AgentCandidateMember.candidate_id == candidate.id,
                RoomMember.room_id == room_id,
                # latest consent round only (earlier rounds are invalidated)
                AgentCandidateMember.consent_round
                == select(func.max(AgentCandidateMember.consent_round))
                .where(AgentCandidateMember.candidate_id == candidate.id)
                .scalar_subquery(),
            )
            .order_by(RoomMember.id)
        ).scalars()
        candidate_dtos.append(
            AgentCandidateDto(
                candidateId=candidate.id,
                rank=candidate.rank,
                sourceRevision=candidate.source_revision,
                sourceSnapshotHash=candidate.source_snapshot_hash,
                startsAt=candidate.starts_at,
                endsAt=candidate.ends_at,
                timeZone=candidate.time_zone,
                candidateType=candidate.candidate_type,
                solverStatus=candidate.solver_status,
                maximumAttendeesProven=candidate.maximum_attendees_proven,
                verified=candidate.verified,
                members=[
                    AgentCandidateMemberDto(
                        roomMemberId=member.room_member_id,
                        participationStatus=member.participation_status,
                        consentRound=member.consent_round,
                        consentStatus=member.consent_status,
                        consentedAt=member.consented_at,
                    )
                    for member in members
                ],
            )
        )
    return AgentCandidateList(
        runId=run.id, status=run.status, candidates=candidate_dtos
    )


@router.post("/{run_id}/cancel", response_model=AgentRunCancellation)
def cancel_agent_run(
    room_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session, scope="function"),
) -> AgentRunCancellation:
    actor = _authorized_member(
        db, room_id=room_id, authorization=authorization
    )
    run = _load_run(db, room_id=room_id, run_id=run_id)
    if not actor.is_host and run.created_by_member_id != actor.room_member_id:
        raise HTTPException(
            status_code=403, detail={"code": "AGENT_RUN_CANCEL_FORBIDDEN"}
        )
    try:
        changed = request_agent_run_cancel_in_session(db, run_id=run.id)
    except AgentRunNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail={"code": exc.code}
        ) from exc
    if not changed:
        db.refresh(run)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "AGENT_RUN_NOT_CANCELLABLE",
                "status": run.status,
            },
        )
    return AgentRunCancellation(
        runId=run.id,
        status=run.status,
        cancelRequested=run.cancel_requested_at is not None,
    )


# --------------------------------------------------------------------------
# Decision flow: select -> consent -> approval -> finalize (DB is authoritative)

_checkpointer_override = None
_checkpointer_singleton = None
# The ExitStack owns the pool; it must stay referenced for the process lifetime or
# garbage collection closes the pool and every later checkpoint call fails.
_checkpointer_stack = None


def _checkpointer():
    """Durable saver for graph sync, or None (DB-only decisions, sync N/A).

    Enabled with AGENT_CHECKPOINT_DATABASE_URL (PostgreSQL); one reconnecting
    pool for the process lifetime. Tests may set _checkpointer_override.
    """
    global _checkpointer_singleton, _checkpointer_stack
    if _checkpointer_override is not None:
        return _checkpointer_override
    url = os.getenv("AGENT_CHECKPOINT_DATABASE_URL")
    if not url:
        return None
    if _checkpointer_singleton is None:
        from contextlib import ExitStack

        from potato_agent.checkpoint import open_postgres_checkpointer

        _checkpointer_stack = ExitStack()
        _checkpointer_singleton = _checkpointer_stack.enter_context(
            open_postgres_checkpointer(url)
        )
    return _checkpointer_singleton


class AttendeeDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    room_member_id: str = Field(alias="roomMemberId")
    consent_status: str | None = Field(alias="consentStatus")


class DecisionStateDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    status: str
    approval_status: str = Field(alias="approvalStatus")
    selected_candidate_id: str | None = Field(alias="selectedCandidateId")
    consent_round: int | None = Field(alias="consentRound")
    decision_version: int = Field(alias="decisionVersion")
    attendees: list[AttendeeDto]
    all_agreed: bool = Field(alias="allAgreed")
    finalized: bool
    graph_sync: str = Field(alias="graphSync")
    changed: bool = False


class SelectCandidateBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    candidate_id: str = Field(alias="candidateId")
    expected_version: int | None = Field(default=None, alias="expectedVersion")


class ConsentBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    decision: str
    expected_version: int | None = Field(default=None, alias="expectedVersion")


class ApprovalBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    decision: str
    expected_version: int | None = Field(default=None, alias="expectedVersion")


class FinalizeBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    expected_version: int | None = Field(default=None, alias="expectedVersion")


def _account_id(authorization: str | None) -> str:
    with open_session() as db, db.begin():
        return account_from_authorization(db, authorization).id


def _decision_dto(state, *, changed: bool = False) -> DecisionStateDto:
    return DecisionStateDto(
        runId=state.run_id,
        status=state.status,
        approvalStatus=state.approval_status,
        selectedCandidateId=state.selected_candidate_id,
        consentRound=state.consent_round,
        decisionVersion=state.decision_version,
        attendees=[
            AttendeeDto(roomMemberId=a.room_member_id, consentStatus=a.consent_status)
            for a in state.attendees
        ],
        allAgreed=state.all_agreed,
        finalized=state.finalized,
        graphSync=state.graph_sync,
        changed=changed,
    )


def _decision_call(call, **kwargs) -> DecisionStateDto:
    try:
        result = call(open_session, _checkpointer(), **kwargs)
    except agent_decision.DecisionError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
    except AgentRunServiceError as exc:
        _raise_service_error(exc)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
    except (AgentSnapshotRevalidationError, SnapshotBuildError) as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_MEETING_SNAPSHOT"}
        ) from exc
    return _decision_dto(result.state, changed=result.changed)


@router.get("/{run_id}/decision", response_model=DecisionStateDto)
def get_decision(
    room_id: str, run_id: str, authorization: str | None = Header(default=None)
) -> DecisionStateDto:
    account_id = _account_id(authorization)
    try:
        state = agent_decision.get_decision_state(
            open_session, run_id=run_id, room_id=room_id, actor_account_id=account_id
        )
    except AgentRunServiceError as exc:
        _raise_service_error(exc)
    except AgentRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code}) from exc
    return _decision_dto(state)


@router.post("/{run_id}/select", response_model=DecisionStateDto)
def select_candidate(
    room_id: str, run_id: str, body: SelectCandidateBody,
    authorization: str | None = Header(default=None),
) -> DecisionStateDto:
    return _decision_call(
        agent_decision.select_candidate, run_id=run_id, room_id=room_id,
        actor_account_id=_account_id(authorization),
        candidate_id=body.candidate_id, expected_version=body.expected_version,
    )


@router.post("/{run_id}/consent", response_model=DecisionStateDto)
def record_consent(
    room_id: str, run_id: str, body: ConsentBody,
    authorization: str | None = Header(default=None),
) -> DecisionStateDto:
    if body.decision not in ("AGREE", "DISAGREE", "WITHDRAW"):
        raise HTTPException(status_code=422, detail={"code": "INVALID_CONSENT_DECISION"})
    return _decision_call(
        agent_decision.record_consent, run_id=run_id, room_id=room_id,
        actor_account_id=_account_id(authorization),
        decision=body.decision, expected_version=body.expected_version,
    )


@router.post("/{run_id}/approval", response_model=DecisionStateDto)
def decide_approval(
    room_id: str, run_id: str, body: ApprovalBody,
    authorization: str | None = Header(default=None),
) -> DecisionStateDto:
    if body.decision not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=422, detail={"code": "INVALID_APPROVAL_DECISION"})
    return _decision_call(
        agent_decision.decide_approval, run_id=run_id, room_id=room_id,
        actor_account_id=_account_id(authorization),
        decision=body.decision, expected_version=body.expected_version,
    )


@router.post("/{run_id}/finalize", response_model=DecisionStateDto)
def finalize_meeting(
    room_id: str, run_id: str, body: FinalizeBody,
    authorization: str | None = Header(default=None),
) -> DecisionStateDto:
    return _decision_call(
        agent_decision.finalize_meeting, run_id=run_id, room_id=room_id,
        actor_account_id=_account_id(authorization),
        expected_version=body.expected_version,
    )


# --------------------------------------------------------------------------
# Canonical final result of the Agent flow for the room's current round

final_router = APIRouter(prefix="/v2/rooms/{room_id}", tags=["Agent final result"])


class FinalResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    finalized: bool
    coordination_round: int = Field(alias="coordinationRound")
    room_round: int = Field(alias="roomRound")  # deprecated alias of coordinationRound
    room_progress_status: str = Field(alias="roomProgressStatus")
    room_lifecycle_status: str = Field(alias="roomLifecycleStatus")
    current_input_revision: int = Field(alias="currentInputRevision")
    run_id: str | None = Field(default=None, alias="runId")
    candidate_id: str | None = Field(default=None, alias="candidateId")
    starts_at: datetime | None = Field(default=None, alias="startsAt")
    ends_at: datetime | None = Field(default=None, alias="endsAt")
    time_zone: str | None = Field(default=None, alias="timeZone")
    candidate_type: str | None = Field(default=None, alias="candidateType")
    attendee_member_ids: list[str] = Field(default_factory=list, alias="attendeeMemberIds")
    approved_by_member_id: str | None = Field(default=None, alias="approvedByMemberId")
    approved_at: datetime | None = Field(default=None, alias="approvedAt")
    finalized_by_member_id: str | None = Field(default=None, alias="finalizedByMemberId")
    finalized_at: datetime | None = Field(default=None, alias="finalizedAt")
    input_revision: int | None = Field(default=None, alias="inputRevision")
    input_current: bool | None = Field(default=None, alias="inputCurrent")


@final_router.get("/agent-final-result", response_model=FinalResultDto)
def get_agent_final_result(
    room_id: str, authorization: str | None = Header(default=None)
) -> FinalResultDto:
    account_id = _account_id(authorization)
    try:
        result = agent_decision.get_final_result(
            open_session, room_id=room_id, actor_account_id=account_id
        )
    except AgentRunServiceError as exc:
        _raise_service_error(exc)
    return FinalResultDto(
        finalized=result.finalized,
        coordinationRound=result.coordination_round,
        roomRound=result.coordination_round,
        roomProgressStatus=result.room_progress_status,
        roomLifecycleStatus=result.room_lifecycle_status,
        currentInputRevision=result.current_input_revision,
        runId=result.run_id,
        candidateId=result.candidate_id,
        startsAt=result.starts_at,
        endsAt=result.ends_at,
        timeZone=result.time_zone,
        candidateType=result.candidate_type,
        attendeeMemberIds=list(result.attendee_member_ids),
        approvedByMemberId=result.approved_by_member_id,
        approvedAt=result.approved_at,
        finalizedByMemberId=result.finalized_by_member_id,
        finalizedAt=result.finalized_at,
        inputRevision=result.input_revision,
        inputCurrent=result.input_current,
    )


class OpenRoundBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    expected_round: int = Field(alias="expectedRound")
    reason: str | None = None


class RoundOpeningDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    from_round: int = Field(alias="fromRound")
    to_round: int = Field(alias="toRound")
    opened_input_revision: int = Field(alias="openedInputRevision")
    closed_run_id: str | None = Field(alias="closedRunId")
    reason: str | None
    created_at: datetime = Field(alias="createdAt")
    changed: bool


@final_router.post("/coordination-rounds", response_model=RoundOpeningDto)
def open_coordination_round(
    room_id: str,
    body: OpenRoundBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RoundOpeningDto:
    account_id = _account_id(authorization)  # authenticate first
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED"})
    try:
        opening = coordination_round.open_next_coordination_round(
            open_session,
            room_id=room_id,
            actor_account_id=account_id,
            idempotency_key=idempotency_key,
            expected_round=body.expected_round,
            reason=body.reason,
        )
    except coordination_round.RoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
    except AgentRunServiceError as exc:
        _raise_service_error(exc)
    return RoundOpeningDto(
        id=opening.id,
        fromRound=opening.from_round,
        toRound=opening.to_round,
        openedInputRevision=opening.opened_input_revision,
        closedRunId=opening.closed_run_id,
        reason=opening.reason,
        createdAt=opening.created_at,
        changed=opening.changed,
    )
