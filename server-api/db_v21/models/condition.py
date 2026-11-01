"""Condition submissions, available slots, role preferences."""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class ConditionSubmission(Base):
    __tablename__ = "condition_submissions"
    __table_args__ = (
        UniqueConstraint(
            "room_member_id",
            "version",
            name="uq_condition_submissions_member_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    ai_draft_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_drafts.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConditionAvailableSlot(Base):
    __tablename__ = "condition_available_slots"
    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at", name="ck_condition_available_slots_range"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    condition_submission_id: Mapped[str] = mapped_column(
        ForeignKey("condition_submissions.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConditionRolePreference(Base):
    __tablename__ = "condition_role_preferences"
    __table_args__ = (
        CheckConstraint(
            "preference IN ('PREFERRED', 'AVAILABLE', 'AVOID')",
            name="ck_condition_role_preferences_preference",
        ),
    )

    condition_submission_id: Mapped[str] = mapped_column(
        ForeignKey("condition_submissions.id", ondelete="CASCADE"), primary_key=True
    )
    room_role_id: Mapped[str] = mapped_column(
        ForeignKey("room_roles.id", ondelete="CASCADE"), primary_key=True
    )
    preference: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
