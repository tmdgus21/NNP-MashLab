"""Authenticated endpoints for natural-language change proposals."""
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from database import session as open_session
from services import agent_change
from services.agent_run import AgentRunServiceError
from services.meeting_snapshot import SnapshotBuildError
from user_auth import account_from_authorization

router = APIRouter(
    prefix="/v2/rooms/{room_id}/agent-change-proposals", tags=["Agent change proposals"]
)


class CreateProposalBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_text: str = Field(alias="requestText")


class ProposalDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    proposal_id: str = Field(alias="proposalId")
    status: str
    base_input_revision: int = Field(alias="baseInputRevision")
    summary: str
    changes: list[dict]
    ambiguities: list[str]
    requested_by_member_id: str = Field(alias="requestedByMemberId")
    resulting_run_id: str | None = Field(alias="resultingRunId")
    applied_input_revision: int | None = Field(alias="appliedInputRevision")
    created_at: datetime = Field(alias="createdAt")
    decided_at: datetime | None = Field(alias="decidedAt")
    changed: bool


def _dto(record: agent_change.ProposalRecord) -> ProposalDto:
    return ProposalDto(
        proposalId=record.id,
        status=record.status,
        baseInputRevision=record.base_revision,
        summary=record.summary,
        changes=list(record.changes),
        ambiguities=list(record.ambiguities),
        requestedByMemberId=record.requested_by_member_id,
        resultingRunId=record.resulting_run_id,
        appliedInputRevision=record.applied_revision,
        createdAt=record.created_at,
        decidedAt=record.decided_at,
        changed=record.changed,
    )


def _account_id(authorization: str | None) -> str:
    with open_session() as db, db.begin():
        return account_from_authorization(db, authorization).id


def _call(fn, **kwargs) -> ProposalDto:
    try:
        return _dto(fn(open_session, **kwargs))
    except agent_change.ChangeError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
    except AgentRunServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
    except SnapshotBuildError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_MEETING_SNAPSHOT"}
        ) from exc


@router.post("", response_model=ProposalDto)
def create_proposal(
    room_id: str,
    body: CreateProposalBody,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ProposalDto:
    account_id = _account_id(authorization)  # authenticate before anything else
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED"})
    return _call(
        agent_change.create_change_proposal,
        room_id=room_id,
        actor_account_id=account_id,
        idempotency_key=idempotency_key,
        request_text=body.request_text,
    )


@router.get("/{proposal_id}", response_model=ProposalDto)
def get_proposal(
    room_id: str, proposal_id: str, authorization: str | None = Header(default=None)
) -> ProposalDto:
    return _call(
        agent_change.get_change_proposal,
        room_id=room_id, proposal_id=proposal_id,
        actor_account_id=_account_id(authorization),
    )


@router.post("/{proposal_id}/approve", response_model=ProposalDto)
def approve_proposal(
    room_id: str, proposal_id: str, authorization: str | None = Header(default=None)
) -> ProposalDto:
    return _call(
        agent_change.approve_change_proposal,
        room_id=room_id, proposal_id=proposal_id,
        actor_account_id=_account_id(authorization),
    )


@router.post("/{proposal_id}/reject", response_model=ProposalDto)
def reject_proposal(
    room_id: str, proposal_id: str, authorization: str | None = Header(default=None)
) -> ProposalDto:
    return _call(
        agent_change.reject_change_proposal,
        room_id=room_id, proposal_id=proposal_id,
        actor_account_id=_account_id(authorization),
    )
