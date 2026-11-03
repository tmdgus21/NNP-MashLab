"""Additive storage for Qwen-originated change proposals.

Revision ID: 20261103_0009
Revises: 20261103_0008
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261103_0009"
down_revision: Union[str, Sequence[str], None] = "20261103_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_CHECK = (
    "status IN ('PROPOSED','CLARIFICATION_REQUIRED','MODEL_REJECTED',"
    "'APPLIED','REJECTED','SUPERSEDED')"
)


def upgrade() -> None:
    op.create_table(
        "agent_change_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(36),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_member_id",
            sa.String(36),
            sa.ForeignKey("room_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("base_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "decided_by_member_id",
            sa.String(36),
            sa.ForeignKey("room_members.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_revision", sa.Integer(), nullable=True),
        sa.Column(
            "resulting_run_id",
            sa.String(36),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_agent_change_proposals_status"),
        sa.CheckConstraint(
            "base_revision >= 1", name="ck_agent_change_proposals_base_revision"
        ),
        sa.CheckConstraint(
            "length(base_snapshot_hash) = 64",
            name="ck_agent_change_proposals_hash_length",
        ),
        sa.UniqueConstraint(
            "room_id",
            "requested_by_member_id",
            "idempotency_key_hash",
            name="uq_agent_change_proposals_idempotency",
        ),
    )
    op.create_index(
        "ix_agent_change_proposals_room_id", "agent_change_proposals", ["room_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_change_proposals_room_id", table_name="agent_change_proposals")
    op.drop_table("agent_change_proposals")
