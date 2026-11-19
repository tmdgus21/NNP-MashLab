"""Potato Meet scheduling tables (deterministic coordination).

See docs/potato-meet/data-model.md. SSE DB outbox is deferred (not modeled here).
SLOT_MINUTES=30 is enforced in service code, not DB CHECKs on timestamps.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class ScheduleCollection(Base):
    __tablename__ = "schedule_collections"
    __table_args__ = (
        UniqueConstraint("room_id", "cycle", name="uq_schedule_collections_room_cycle"),
        CheckConstraint("cycle BETWEEN 0 AND 4", name="ck_schedule_collections_cycle"),
        CheckConstraint("kind IN ('NORMAL', 'READJUST')", name="ck_schedule_collections_kind"),
        CheckConstraint("scope_ends_at > scope_starts_at", name="ck_schedule_collections_scope"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_schedule_collections_status"),
        CheckConstraint(
            "closed_reason IS NULL OR closed_reason IN ('ALL_DONE', 'DEADLINE')",
            name="ck_schedule_collections_closed_reason",
        ),
        CheckConstraint(
            "extended_count BETWEEN 0 AND 1",
            name="ck_schedule_collections_extended_count",
        ),
        Index(
            "uq_schedule_collections_open_room",
            "room_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
            sqlite_where=text("status = 'OPEN'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    cycle: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    hints_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    scope_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scope_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    grace_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extended_count: Mapped[int] = mapped_column(Integer, default=0)


class ScheduleResponse(Base):
    __tablename__ = "schedule_responses"

    collection_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_collections.id", ondelete="CASCADE"), primary_key=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), primary_key=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ScheduleResponseRange(Base):
    __tablename__ = "schedule_response_ranges"
    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at", name="ck_schedule_response_ranges_range"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_collections.id", ondelete="CASCADE"), index=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        CheckConstraint(
            "closed_reason IS NULL OR closed_reason IN ('ALL_VOTED', 'TIMEOUT')",
            name="ck_schedule_runs_closed_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("schedule_collections.id", ondelete="SET NULL"), nullable=True
    )
    max_count: Mapped[int] = mapped_column(Integer)
    participant_count: Mapped[int] = mapped_column(Integer)
    voter_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    voting_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voting_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    excluded_soon_count: Mapped[int] = mapped_column(Integer, default=0)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ScheduleCandidate(Base):
    __tablename__ = "schedule_candidates"
    __table_args__ = (
        UniqueConstraint("run_id", "sort_order", name="uq_schedule_candidates_run_sort"),
        CheckConstraint("ends_at > starts_at", name="ck_schedule_candidates_range"),
        CheckConstraint(
            "available_count >= 2", name="ck_schedule_candidates_available_count"
        ),
        CheckConstraint("sort_order > 0", name="ck_schedule_candidates_sort_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_runs.id", ondelete="CASCADE"), index=True
    )
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_count: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer)


class ScheduleCandidateMember(Base):
    __tablename__ = "schedule_candidate_members"

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_candidates.id", ondelete="CASCADE"), primary_key=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), primary_key=True
    )


class ScheduleVote(Base):
    __tablename__ = "schedule_votes"

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_candidates.id", ondelete="CASCADE"), primary_key=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), primary_key=True
    )
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    voted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ScheduleVoteBallot(Base):
    """Marks vote completion for a run; empty ballot has a row with no schedule_votes."""

    __tablename__ = "schedule_vote_ballots"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_runs.id", ondelete="CASCADE"), primary_key=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), primary_key=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ScheduleResult(Base):
    __tablename__ = "schedule_results"
    __table_args__ = (
        CheckConstraint(
            "method IN ('AUTO', 'VOTE')", name="ck_schedule_results_method"
        ),
    )

    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("schedule_candidates.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(10))
    vote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tie_broken: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PushDevice(Base):
    __tablename__ = "push_devices"
    __table_args__ = (
        CheckConstraint("platform IN ('ANDROID')", name="ck_push_devices_platform"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(512), unique=True)
    platform: Mapped[str] = mapped_column(String(10), default="ANDROID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    start_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    remind_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    extend_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class NotificationLog(Base):
    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "kind",
            "event_key",
            "account_id",
            name="uq_notification_log_dedupe",
        ),
        CheckConstraint(
            "kind IN ('START', 'REMIND', 'EXTEND')", name="ck_notification_log_kind"
        ),
        CheckConstraint(
            "status IN ('QUEUED', 'SENT', 'FAILED', 'SKIPPED')",
            name="ck_notification_log_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(10))
    event_key: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10), default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
