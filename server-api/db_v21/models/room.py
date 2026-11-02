"""Rooms, members, roles.

Idempotency for create/join mirrors ok_members: request_key_hash + request_hash on
room_members. Same key with different payload → 409; same key+payload → replay.
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
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
        CheckConstraint(
            "progress_status IN ("
            "'collecting','reviewing','finalized','deleted','cancelled')",
            name="ck_rooms_progress_status",
        ),
        CheckConstraint(
            "agent_input_revision >= 1",
            name="ck_rooms_agent_input_revision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    created_by_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # OWNER room_member id (API hostId); kept denormalized for host checks without joins
    host_member_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lifecycle_status: Mapped[str] = mapped_column(
        String(40), default="COLLECTING_CONDITIONS"
    )
    # API-facing progress (legacy ok_rooms.status)
    progress_status: Mapped[str] = mapped_column(String(20), default="collecting")
    # CreateMeeting dump + _lifecycle admin cycle metadata
    meeting_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    dirty: Mapped[bool] = mapped_column(Boolean, default=True)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    agent_input_revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1")
    )
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
        Index("ix_room_members_request_key_hash", "request_key_hash", unique=True),
        Index("ix_room_members_token_hash", "token_hash", unique=True),
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
    # Meeting-scoped bearer token (workflow compatibility with ok_members.token_hash)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Idempotency for create/join (from ok_members)
    request_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
