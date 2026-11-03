"""Additive Agent decision persistence: candidate link, version CAS, sync lease.

Revision ID: 20261103_0008
Revises: 20261102_0007
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261103_0008"
down_revision: Union[str, Sequence[str], None] = "20261102_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _restore_snapshot_trigger() -> None:
    # batch_alter_table recreates agent_runs on SQLite and drops its trigger.
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER trg_agent_run_snapshot_immutable
            BEFORE UPDATE OF source_revision, input_snapshot_hash, input_snapshot
            ON agent_runs
            WHEN NEW.source_revision IS NOT OLD.source_revision
              OR NEW.input_snapshot_hash IS NOT OLD.input_snapshot_hash
              OR NEW.input_snapshot IS NOT OLD.input_snapshot
            BEGIN
              SELECT RAISE(ABORT, 'agent run snapshot is immutable');
            END
            """
        )


def upgrade() -> None:
    # Plain ADD COLUMN only: existing rows keep working and no table rebuild
    # (so the SQLite immutability trigger is untouched).
    op.add_column(
        "agent_candidates",
        sa.Column("graph_candidate_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "uq_agent_candidates_run_graph_id",
        "agent_candidates",
        ["run_id", "graph_candidate_id"],
        unique=True,
    )
    for column in (
        sa.Column("decision_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("graph_synced_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sync_owner", sa.String(36), nullable=True),
        sa.Column("sync_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("base_checkpoint_ref", sa.String(256), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_by_member_id", sa.String(36), nullable=True),
    ):
        op.add_column("agent_runs", column)


def downgrade() -> None:
    op.drop_index("uq_agent_candidates_run_graph_id", table_name="agent_candidates")
    with op.batch_alter_table("agent_candidates") as batch:
        batch.drop_column("graph_candidate_id")
    with op.batch_alter_table("agent_runs") as batch:
        for name in (
            "finalized_by_member_id",
            "finalized_at",
            "base_checkpoint_ref",
            "sync_lease_expires_at",
            "sync_owner",
            "graph_synced_version",
            "decision_version",
        ):
            batch.drop_column(name)
    _restore_snapshot_trigger()
