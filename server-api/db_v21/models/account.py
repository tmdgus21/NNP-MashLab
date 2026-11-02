"""Accounts, sessions, password reset tokens."""
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('USER', 'ADMIN', 'GUEST')",
            name="ck_accounts_account_type",
        ),
        CheckConstraint(
            "account_status IN ('ACTIVE', 'DISABLED', 'FROZEN')",
            name="ck_accounts_account_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    login_email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    account_type: Mapped[str] = mapped_column(String(20), default="USER")
    account_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    # Admin-security fields (used when account_type=ADMIN; preserved from ok_admin_accounts)
    admin_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AccountSession(Base):
    __tablename__ = "account_sessions"
    # expires_at may be moved into the past to force logout; no created/expires check.

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at", name="ck_password_reset_tokens_expires"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
