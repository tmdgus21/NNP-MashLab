<<<<<<< HEAD
"""Admin controls, audit, announcements, and security extras (OTP/rate/cycles)."""
=======
"""Admin controls, audit, announcements, OTP/rate limits, and idempotency ledger.

No room_cycles / room_cycle_archives: one event per room; re-assignment uses proposals.round.
Admin extension and other non-join mutations use idempotency_records.
"""
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
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


class ServiceControl(Base):
    __tablename__ = "service_controls"
    __table_args__ = (
        CheckConstraint(
            "control_status IN ('ENABLED', 'DISABLED', 'READ_ONLY')",
            name="ck_service_controls_status",
        ),
    )

    feature_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    control_status: Mapped[str] = mapped_column(String(20), default="ENABLED")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class RoomControl(Base):
    __tablename__ = "room_controls"
    __table_args__ = (
        CheckConstraint(
            "control_status IN ('ACTIVE', 'SUSPENDED')",
            name="ck_room_controls_status",
        ),
    )

    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True
    )
    control_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by_admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    admin_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_type: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str] = mapped_column(String(50), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')",
            name="ck_announcements_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_by_admin_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(40), default="ALL")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AdminOtp(Base):
<<<<<<< HEAD
    """Preserved from ok_admin_otps — not in core 19 tables."""
=======
    """Preserved from ok_admin_otps."""
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284

    __tablename__ = "admin_otps"

    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    challenge: Mapped[str] = mapped_column(String(64), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class AdminRateLimit(Base):
<<<<<<< HEAD
    """Preserved from ok_admin_rate_limits — not in core 19 tables."""
=======
    """Preserved from ok_admin_rate_limits."""
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284

    __tablename__ = "admin_rate_limits"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    reset: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


<<<<<<< HEAD
class RoomCycleArchive(Base):
    """Preserved from ok_room_cycles — admin cycle snapshots."""

    __tablename__ = "room_cycle_archives"
    __table_args__ = (
        UniqueConstraint("room_id", "cycle", name="uq_room_cycle_archives_room_cycle"),
        UniqueConstraint(
            "room_id", "request_key", name="uq_room_cycle_archives_room_request"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    cycle: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
=======
class IdempotencyRecord(Base):
    """Duplicate-request ledger for non-join mutations (admin extend, etc.).

    Replaces ok_room_cycles request_key/request_hash pairing without multi-event cycles.
    """

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "key_hash", name="uq_idempotency_records_scope_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    scope: Mapped[str] = mapped_column(String(64))
    key_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Replay payload (e.g. extension cycle snapshot); optional
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
