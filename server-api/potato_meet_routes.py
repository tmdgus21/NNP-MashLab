"""Potato Meet entry API: create / join / invite / RSVP / availability.

Authentication is the existing v2.1 account bearer token (/v1/auth/login).
"""
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from database import session as open_session
from services import agent_change, potato_meet
from services.agent_run import AgentRunServiceError
from services.meeting_snapshot import SnapshotBuildError
from user_auth import account_from_authorization

router = APIRouter(prefix="/v2", tags=["Potato Meet"])


def _account_id(authorization: str | None) -> str:
    with open_session() as db, db.begin():
        return account_from_authorization(db, authorization).id


def _call(fn, **kwargs):
    try:
        return fn(open_session, **kwargs)
    except (potato_meet.PotatoError, agent_change.ChangeError) as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
    except AgentRunServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code}) from exc
    except SnapshotBuildError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_MEETING_SNAPSHOT"}) from exc


class JoinBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=16)
    nickname: str = Field(min_length=1, max_length=30)


class InviteBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    account_ids: list[str] = Field(alias="accountIds", min_length=1, max_length=20)
    send: bool = True


class ExcludeBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    account_id: str = Field(alias="accountId")
    reason: str = Field(min_length=1, max_length=200)


class RespondBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: Literal["ACCEPTED", "DECLINED"]
    nickname: str | None = Field(default=None, max_length=30)


class MinimumBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    minimum_attendee_count: StrictInt = Field(alias="minimumAttendeeCount")
    expected_input_revision: StrictInt | None = Field(default=None, alias="expectedInputRevision")


@router.post("/rooms", status_code=201)
def create_room(
    body: potato_meet.CreateRoomRequest,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    account_id = _account_id(authorization)  # authenticate first
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED"})
    view = _call(
        potato_meet.create_room, account_id=account_id,
        idempotency_key=idempotency_key, request=body,
    )
    if view["replayed"]:
        response.status_code = 200
    return view


@router.get("/rooms")
def list_rooms(
    limit: int = Query(default=50, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    return _call(potato_meet.list_my_rooms, account_id=_account_id(authorization), limit=limit)


@router.get("/rooms/{room_id}/latest-run")
def latest_run(room_id: str, authorization: str | None = Header(default=None)):
    return _call(potato_meet.latest_run, room_id=room_id, account_id=_account_id(authorization))


@router.post("/rooms/{room_id}/leave")
def leave(room_id: str, authorization: str | None = Header(default=None)):
    return _call(potato_meet.leave_room, room_id=room_id, account_id=_account_id(authorization))


@router.post("/rooms/join")
def join_room(body: JoinBody, authorization: str | None = Header(default=None)):
    return _call(
        potato_meet.join_room, account_id=_account_id(authorization),
        code=body.code, nickname=body.nickname,
    )


@router.get("/rooms/{room_id}")
def get_room(room_id: str, authorization: str | None = Header(default=None)):
    return _call(potato_meet.get_room, room_id=room_id, account_id=_account_id(authorization))


@router.get("/rooms/{room_id}/participants")
def list_participants(room_id: str, authorization: str | None = Header(default=None)):
    return _call(potato_meet.list_participants, room_id=room_id, account_id=_account_id(authorization))


@router.post("/rooms/{room_id}/invitations")
def invite(room_id: str, body: InviteBody, authorization: str | None = Header(default=None)):
    return _call(
        potato_meet.invite_accounts, room_id=room_id,
        actor_account_id=_account_id(authorization),
        account_ids=body.account_ids, send=body.send,
    )


@router.post("/rooms/{room_id}/invitations/exclude")
def exclude(room_id: str, body: ExcludeBody, authorization: str | None = Header(default=None)):
    return _call(
        potato_meet.exclude_pending_invitee, room_id=room_id,
        actor_account_id=_account_id(authorization), account_id=body.account_id, reason=body.reason,
    )


@router.put("/rooms/{room_id}/invitations/me")
def respond(room_id: str, body: RespondBody, authorization: str | None = Header(default=None)):
    return _call(
        potato_meet.respond_to_invitation, room_id=room_id,
        account_id=_account_id(authorization), response=body.response, nickname=body.nickname,
    )


@router.get("/people/recent")
def recent_people(
    q: str | None = Query(default=None, max_length=30),
    roomId: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    return _call(
        potato_meet.list_recent_people, account_id=_account_id(authorization),
        query=q, for_room_id=roomId, limit=limit,
    )


@router.get("/room-invitations/me")
def my_invitations(authorization: str | None = Header(default=None)):
    return _call(potato_meet.list_my_invitations, account_id=_account_id(authorization))


@router.put("/rooms/{room_id}/minimum-attendees")
def set_minimum(room_id: str, body: MinimumBody, authorization: str | None = Header(default=None)):
    return _call(
        potato_meet.set_minimum_attendees, room_id=room_id,
        actor_account_id=_account_id(authorization),
        minimum=body.minimum_attendee_count,
        expected_input_revision=body.expected_input_revision,
    )


@router.get("/rooms/{room_id}/availability/me")
def get_availability(room_id: str, authorization: str | None = Header(default=None)):
    return _call(
        potato_meet.get_my_availability, room_id=room_id, account_id=_account_id(authorization)
    )


@router.put("/rooms/{room_id}/availability/me")
def put_availability(
    room_id: str,
    body: potato_meet.SubmitAvailabilityRequest,
    authorization: str | None = Header(default=None),
):
    return _call(
        potato_meet.submit_my_availability, room_id=room_id,
        account_id=_account_id(authorization), request=body,
    )
