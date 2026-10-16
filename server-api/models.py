"""Operational Conditional OK schema (ok_*). Single source for ORM + Alembic."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Room(Base):
    __tablename__ = "ok_rooms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    host_id: Mapped[str] = mapped_column(String(36))
    config: Mapped[dict] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    round: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="collecting")
    dirty: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Member(Base):
    __tablename__ = "ok_members"
    __table_args__ = (
        UniqueConstraint("room_id", "nickname"),
        Index("ix_ok_members_request_key_hash", "request_key_hash", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(ForeignKey("ok_rooms.id"), index=True)
    nickname: Mapped[str] = mapped_column(String(30))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    request_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AIDraft(Base):
    __tablename__ = "ok_ai_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    member_id: Mapped[str] = mapped_column(ForeignKey("ok_members.id"), index=True)
    raw_text: Mapped[str] = mapped_column(String(1500))
    model_output: Mapped[dict] = mapped_column(JSON)
    app_draft: Mapped[dict] = mapped_column(JSON)
    questions: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Submission(Base):
    __tablename__ = "ok_condition_submissions"
    __table_args__ = (UniqueConstraint("member_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    member_id: Mapped[str] = mapped_column(ForeignKey("ok_members.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    confirmed: Mapped[dict] = mapped_column(JSON)
    ai_draft_id: Mapped[str | None] = mapped_column(ForeignKey("ok_ai_drafts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Proposal(Base):
    __tablename__ = "ok_proposals"
    __table_args__ = (UniqueConstraint("room_id", "round"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(ForeignKey("ok_rooms.id"), index=True)
    round: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    plan: Mapped[dict] = mapped_column(JSON)
    solver_status: Mapped[str] = mapped_column(String(20))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConsentRow(Base):
    __tablename__ = "ok_consents"
    __table_args__ = (UniqueConstraint("proposal_id", "member_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("ok_proposals.id"), index=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("ok_members.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(String(1000), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RoomEvent(Base):
    __tablename__ = "ok_room_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(ForeignKey("ok_rooms.id"), index=True)
    message: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SchemaVersion(Base):
    """Legacy version marker retained for parity with existing databases."""
    __tablename__ = "ok_schema_versions"
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
