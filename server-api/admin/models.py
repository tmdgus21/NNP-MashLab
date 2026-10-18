"""Additive tables; only the explicit migration command creates these."""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from database import uid, now

class AdminBase(DeclarativeBase): pass
class Account(AdminBase):
    __tablename__ = 'ok_admin_accounts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), default='VIEWER')
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class OTP(AdminBase):
    __tablename__ = 'ok_admin_otps'
    account_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    challenge: Mapped[str] = mapped_column(String(64), unique=True)
    digest: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
class AdminSession(AdminBase):
    __tablename__ = 'ok_admin_sessions'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
class Audit(AdminBase):
    __tablename__ = 'ok_admin_audit'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(50))
    target: Mapped[str] = mapped_column(String(100), index=True)
    reason: Mapped[str] = mapped_column(String(1000), default='')
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
class RateBucket(AdminBase):
    __tablename__ = 'ok_admin_rate_limits'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    reset: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
class Lifecycle(AdminBase):
    __tablename__ = 'ok_room_lifecycle'
    room_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cycle: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(24), default='ACTIVE')
    management: Mapped[str] = mapped_column(String(20), default='ENABLED')
    scheduled_date: Mapped[str] = mapped_column(String(10), index=True)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    base_round: Mapped[int] = mapped_column(Integer, default=-1)
class CycleArchive(AdminBase):
    __tablename__ = 'ok_room_cycles'
    __table_args__ = (UniqueConstraint('room_id', 'cycle'), UniqueConstraint('room_id', 'request_key'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(String(36), index=True)
    cycle: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
