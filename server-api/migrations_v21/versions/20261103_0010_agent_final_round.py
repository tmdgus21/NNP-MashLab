"""Bind an Agent finalization to the room round and allow one per round.

Revision ID: 20261103_0010
Revises: 20261103_0009
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261103_0010"
down_revision: Union[str, Sequence[str], None] = "20261103_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "uq_agent_runs_final_per_room_round"


def upgrade() -> None:
    # Plain ADD COLUMN: no table rebuild, so the SQLite snapshot trigger survives.
    op.add_column(
        "agent_runs", sa.Column("finalized_room_round", sa.Integer(), nullable=True)
    )
    # Fails loudly if a room already has two finalized Runs in one round
    # (impossible before 0008/0010 reach a database; see deploy notes).
    op.create_index(
        _INDEX,
        "agent_runs",
        ["room_id", "finalized_room_round"],
        unique=True,
        sqlite_where=sa.text("finalized_at IS NOT NULL"),
        postgresql_where=sa.text("finalized_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="agent_runs")
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_column("finalized_room_round")
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
