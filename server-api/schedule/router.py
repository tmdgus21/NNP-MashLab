"""Potato Meet schedule HTTP API."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from schedule import service
from schedule.deps import (
    db_session,
    fail,
    load_room,
    require_account,
    require_member,
    require_owner,
)
from schedule.events import format_sse, hub
from schedule.schemas import (
    CreateMeetingIn,
    JoinMeetingIn,
    RevisionIn,
    SubmitResponseIn,
    VoteIn,
)
from schedule.timeutil import to_seoul


def _validation_message(exc: ValidationError) -> str:
    err = exc.errors()[0] if exc.errors() else {}
    msg = str(err.get("msg") or "요청이 올바르지 않습니다.")
    prefix = "Value error, "
    if msg.startswith(prefix):
        return msg[len(prefix) :]
    return msg

router = APIRouter(prefix="/v1", tags=["Potato Meet schedule"])


@router.get("/time")
def get_time():
    return service.server_time_payload()


@router.get("/meetings")
def list_meetings(account=Depends(require_account), db=Depends(db_session)):
    from sqlalchemy import select

    from db_v21.models.room import Room, RoomMember

    rows = db.scalars(
        select(Room)
        .join(RoomMember, RoomMember.room_id == Room.id)
        .where(
            RoomMember.account_id == account.id,
            RoomMember.membership_status == "ACTIVE",
            Room.progress_status != "deleted",
        )
        .order_by(Room.created_at.desc())
    )
    return {
        "meetings": [
            service.meeting_view(db, room, account.id) for room in rows
        ]
    }


def _potato_create_body(body: dict) -> bool:
    return (
        "startDate" in body
        or "start_date" in body
        or "selectedDates" in body
        or "selected_dates" in body
    )


def _potato_join_body(body: dict) -> bool:
    # Potato: {code} or {code, nickname?}; legacy Conditional OK: {code, name}
    return "code" in body and "name" not in body


@router.post("/meetings", status_code=201)
def create_meeting(
    body: dict,
    db=Depends(db_session),
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    x_account_authorization: str | None = Header(default=None),
):
    """Potato Meet create, or legacy workflow create when body is Conditional OK shaped."""
    if _potato_create_body(body):
        from user_auth import account_from_authorization

        account = account_from_authorization(db, authorization)
        try:
            parsed = CreateMeetingIn.model_validate(body)
        except ValidationError as exc:
            fail(422, _validation_message(exc))
        return service.create_meeting(db, account, parsed)
    from workflow import create_meeting as legacy_create
    from workflow_models import CreateMeeting

    return legacy_create(
        CreateMeeting.model_validate(body),
        db,
        idempotency_key,
        x_account_authorization,
    )


@router.post("/meetings/join", status_code=201)
def join_meeting(
    body: dict,
    db=Depends(db_session),
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
    x_account_authorization: str | None = Header(default=None),
):
    if _potato_join_body(body):
        from user_auth import account_from_authorization

        account = account_from_authorization(db, authorization)
        parsed = JoinMeetingIn.model_validate(body)
        return service.join_meeting(db, account, parsed)
    from workflow import join_meeting as legacy_join
    from workflow_models import JoinMeeting

    return legacy_join(
        JoinMeeting.model_validate(body),
        db,
        idempotency_key,
        x_account_authorization,
    )


@router.get("/meetings/{room_id}")
def get_meeting(
    room_id: str,
    db=Depends(db_session),
    authorization: str | None = Header(default=None),
):
    from db_v21.models.room import Room
    from user_auth import account_from_authorization

    room = db.get(Room, room_id)
    if room is not None and not service._is_legacy_room(db, room):
        account = account_from_authorization(db, authorization)
        room = load_room(db, room_id)
        require_member(db, room, account.id)
        return service.meeting_view(db, room, account.id)
    from workflow import get_meeting as legacy_get

    return legacy_get(room_id, authorization, db)


@router.delete("/meetings/{room_id}")
def delete_meeting(
    room_id: str,
    body: dict,
    db=Depends(db_session),
    authorization: str | None = Header(default=None),
):
    from db_v21.models.room import Room
    from user_auth import account_from_authorization

    room = db.get(Room, room_id)
    if room is not None and not service._is_legacy_room(db, room):
        account = account_from_authorization(db, authorization)
        room = load_room(db, room_id)
        member = require_member(db, room, account.id)
        require_owner(member)
        from db_v21.base import now as utc_now
        from schedule.events import queue_event

        parsed = RevisionIn.model_validate(body)
        if room.progress_status == "deleted":
            return {"deleted": True}
        if room.revision != parsed.expected_revision:
            fail(409, "revision이 일치하지 않습니다.")
        room.progress_status = "deleted"
        room.deleted_at = utc_now()
        room.revision += 1
        queue_event(room.id, "meeting_deleted", room.revision)
        return {"deleted": True}
    from workflow import delete_meeting as legacy_delete
    from workflow_models import Revision

    return legacy_delete(room_id, Revision.model_validate(body), authorization, db)


@router.get("/meetings/{room_id}/collection")
def get_collection(
    room_id: str,
    account=Depends(require_account),
    db=Depends(db_session),
):
    room = load_room(db, room_id)
    member = require_member(db, room, account.id)
    if service._is_legacy_room(db, room):
        fail(409, "이전 앱 모임입니다.")
    return service.collection_view(db, room, member)


@router.put("/meetings/{room_id}/collections/{collection_id}/response")
def put_response(
    room_id: str,
    collection_id: str,
    body: SubmitResponseIn,
    account=Depends(require_account),
    db=Depends(db_session),
):
    room = load_room(db, room_id)
    member = require_member(db, room, account.id)
    available = [(to_seoul(r.start), to_seoul(r.end)) for r in body.available]
    return service.submit_response(db, room, member, collection_id, available)


@router.get("/meetings/{room_id}/candidates")
def get_candidates(
    room_id: str,
    account=Depends(require_account),
    db=Depends(db_session),
):
    room = load_room(db, room_id)
    member = require_member(db, room, account.id)
    return service.candidates_view(db, room, member_id=member.id)


@router.put("/meetings/{room_id}/votes/me")
def put_votes(
    room_id: str,
    body: VoteIn,
    account=Depends(require_account),
    db=Depends(db_session),
):
    room = load_room(db, room_id)
    member = require_member(db, room, account.id)
    return service.submit_votes(db, room, member, body.candidate_ids)


@router.get("/meetings/{room_id}/result")
def get_result(
    room_id: str,
    account=Depends(require_account),
    db=Depends(db_session),
):
    room = load_room(db, room_id)
    require_member(db, room, account.id)
    return service.result_view(db, room)


@router.get("/meetings/{room_id}/events")
async def meeting_events(
    room_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """SSE stream. On reconnect the client refetches REST APIs (no event replay)."""
    from database import session
    from schedule.deps import require_member
    from user_auth import account_from_authorization

    with session() as db:
        account = account_from_authorization(db, authorization)
        room = load_room(db, room_id, for_update=False)
        require_member(db, room, account.id)

    queue = await hub.subscribe(room_id)

    async def gen():
        yield ": connected\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield format_sse(item["event"], item["data"])
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await hub.unsubscribe(room_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
