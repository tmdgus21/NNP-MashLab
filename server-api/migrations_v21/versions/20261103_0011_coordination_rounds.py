"""Potato Meet coordination rounds, independent of /v1 role-assignment rounds.

rooms.current_round is the /v1 role-plan round (every /v1 calculation bumps
it). Agent final results bind to rooms.coordination_round instead.
agent_runs.finalized_room_round (migration 0010) now stores that value.

Revision ID: 20261103_0011
Revises: 20261103_0010
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261103_0011"
down_revision: Union[str, Sequence[str], None] = "20261103_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plain ADD COLUMN with a default: existing rows become round 0.
    op.add_column(
        "rooms",
        sa.Column("coordination_round", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "coordination_rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(36),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_round", sa.Integer(), nullable=False),
        sa.Column("to_round", sa.Integer(), nullable=False),
        sa.Column(
            "opened_by_member_id",
            sa.String(36),
            sa.ForeignKey("room_members.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "closed_run_id",
            sa.String(36),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("opened_input_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("to_round = from_round + 1", name="ck_coordination_rounds_step"),
        sa.CheckConstraint("from_round >= 0", name="ck_coordination_rounds_from"),
        sa.UniqueConstraint("room_id", "to_round", name="uq_coordination_rounds_room_to"),
        sa.UniqueConstraint(
            "room_id", "idempotency_key_hash", name="uq_coordination_rounds_idempotency"
        ),
    )
    op.create_index("ix_coordination_rounds_room_id", "coordination_rounds", ["room_id"])


def downgrade() -> None:
    op.drop_index("ix_coordination_rounds_room_id", table_name="coordination_rounds")
    op.drop_table("coordination_rounds")
    with op.batch_alter_table("rooms") as batch:
        batch.drop_column("coordination_round")
