"""Authenticated HTTP endpoints for queued Agent runs."""
from datetime import datetime
from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db_v21.models.agent import AgentCandidate, AgentCandidateMember, AgentRun
from db_v21.models.room import RoomMember
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
    db: Session = Depends(db_session),
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
        workerDispatch="NOT_CONFIGURED",
    )


@router.get("/{run_id}", response_model=AgentRunStatus)
def get_agent_run(
    room_id: str,
    run_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(db_session),
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
    db: Session = Depends(db_session),
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
    db: Session = Depends(db_session),
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
