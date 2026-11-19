"""Auth and membership dependencies for schedule routes."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select

from database import session
from db_v21.models.room import Room, RoomMember
from user_auth import account_from_authorization


def db_session():
    from schedule.events import drain_pending, publish_pending_sync

    with session() as db, db.begin():
        try:
            yield db
        except Exception:
            drain_pending()
            raise
    # Transaction committed — notify SSE subscribers
    publish_pending_sync()


def fail(status: int, message: str) -> None:
    raise HTTPException(status, detail=message)


def require_account(authorization: str | None = Header(default=None), db=Depends(db_session)):
    return account_from_authorization(db, authorization)


def load_room(db, room_id: str, *, for_update: bool = True) -> Room:
    q = select(Room).where(Room.id == room_id)
    if for_update:
        q = q.with_for_update()
    room = db.scalar(q)
    if not room or room.progress_status == "deleted" or room.deleted_at is not None:
        fail(404, "모임을 찾을 수 없습니다.")
    return room


def require_member(db, room: Room, account_id: str) -> RoomMember:
    member = db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id,
            RoomMember.account_id == account_id,
            RoomMember.membership_status == "ACTIVE",
        )
    )
    if not member:
        fail(404, "모임을 찾을 수 없습니다.")
    return member


def require_owner(member: RoomMember) -> RoomMember:
    if member.room_role != "OWNER":
        fail(403, "방장만 할 수 있습니다.")
    return member
