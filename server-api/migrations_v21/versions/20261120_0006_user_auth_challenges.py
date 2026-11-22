"""Add user_auth_challenges for USER email OTP (additive only).

Revision ID: 20261120_0006
Revises: 20261117_0005
Create Date: 2026-11-20

Does not alter admin_otps or existing accounts rows.
FK account_id uses ON DELETE SET NULL so challenge history survives account removal.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261120_0006"
down_revision: Union[str, Sequence[str], None] = "20261117_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_auth_challenges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("challenge", sa.String(length=64), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.CheckConstraint(
            "purpose IN ('REGISTER', 'LOGIN')",
            name="ck_user_auth_challenges_purpose",
        ),
        sa.CheckConstraint(
            "expires_at > sent_at",
            name="ck_user_auth_challenges_expires",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1",
            name="ck_user_auth_challenges_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge", name="uq_user_auth_challenges_challenge"),
    )
    op.create_index(
        "ix_user_auth_challenges_account_id",
        "user_auth_challenges",
        ["account_id"],
    )
    op.create_index(
        "ix_user_auth_challenges_email",
        "user_auth_challenges",
        ["email"],
    )
    op.create_index(
        "ix_user_auth_challenges_expires_at",
        "user_auth_challenges",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_auth_challenges_expires_at", table_name="user_auth_challenges")
    op.drop_index("ix_user_auth_challenges_email", table_name="user_auth_challenges")
    op.drop_index("ix_user_auth_challenges_account_id", table_name="user_auth_challenges")
    op.drop_table("user_auth_challenges")
