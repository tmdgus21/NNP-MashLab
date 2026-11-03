"""Finalize v2.1 schema: JSON restores, idempotency, drop room_cycle_archives.

Revision ID: 20261101_0002
Revises: 20261101_0001
Create Date: 2026-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_0002"
down_revision: Union[str, Sequence[str], None] = "20261101_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_room_cycle_archives_room_id", table_name="room_cycle_archives")
    op.drop_table("room_cycle_archives")

    op.add_column(
        "ai_drafts",
        sa.Column("model_output", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "ai_drafts",
        sa.Column("app_draft", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "ai_drafts",
        sa.Column("questions", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.add_column(
        "condition_submissions",
        sa.Column("confirmed", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.add_column(
        "proposals",
        sa.Column("input_snapshot", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "proposals",
        sa.Column("plan", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.add_column("room_members", sa.Column("token_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "room_members", sa.Column("request_key_hash", sa.String(length=64), nullable=True)
    )
    op.add_column("room_members", sa.Column("request_hash", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_room_members_token_hash", "room_members", ["token_hash"], unique=True
    )
    op.create_index(
        "ix_room_members_request_key_hash",
        "room_members",
        ["request_key_hash"],
        unique=True,
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key_hash", name="uq_idempotency_records_scope_key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_room_members_request_key_hash", table_name="room_members")
    op.drop_index("ix_room_members_token_hash", table_name="room_members")
    op.drop_column("room_members", "request_hash")
    op.drop_column("room_members", "request_key_hash")
    op.drop_column("room_members", "token_hash")
    op.drop_column("proposals", "plan")
    op.drop_column("proposals", "input_snapshot")
    op.drop_column("condition_submissions", "confirmed")
    op.drop_column("ai_drafts", "questions")
    op.drop_column("ai_drafts", "app_draft")
    op.drop_column("ai_drafts", "model_output")
    op.create_table(
        "room_cycle_archives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id", "cycle", name="uq_room_cycle_archives_room_cycle"),
        sa.UniqueConstraint(
            "room_id", "request_key", name="uq_room_cycle_archives_room_request"
        ),
    )
    op.create_index(
        "ix_room_cycle_archives_room_id", "room_cycle_archives", ["room_id"], unique=False
    )
