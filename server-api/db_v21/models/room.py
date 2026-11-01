"""Rooms, members, roles."""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_rooms_time_range"),
        CheckConstraint(
            "lifecycle_status IN ("
            "'COLLECTING_CONDITIONS','READY_FOR_ASSIGNMENT','WAITING_FOR_CONSENT',"
            "'CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED')",
            name="ck_rooms_lifecycle_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    created_by_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lifecycle_status: Mapped[str] = mapped_column(
        String(40), default="COLLECTING_CONDITIONS"
    )
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (
        UniqueConstraint("room_id", "account_id", name="uq_room_members_room_account"),
        UniqueConstraint("room_id", "nickname", name="uq_room_members_room_nickname"),
        CheckConstraint(
            "room_role IN ('OWNER', 'MEMBER')",
            name="ck_room_members_room_role",
        ),
        CheckConstraint(
            "membership_status IN ('ACTIVE', 'LEFT', 'REMOVED')",
            name="ck_room_members_membership_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    nickname: Mapped[str] = mapped_column(String(30))
    room_role: Mapped[str] = mapped_column(String(20), default="MEMBER")
    membership_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RoomRole(Base):
    __tablename__ = "room_roles"
    __table_args__ = (
        UniqueConstraint("room_id", "name", name="uq_room_roles_room_name"),
        CheckConstraint("required_count > 0", name="ck_room_roles_required_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(30))
    required_count: Mapped[int] = mapped_column(Integer)
