"""Allow durable runs to be queued before Agent execution.

Revision ID: 20261102_0006
Revises: 20261102_0005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_0006"
down_revision: Union[str, Sequence[str], None] = "20261102_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUS_CHECK = (
    "status IN ("
    "'QUEUED','WAITING_FOR_INPUT','ANALYZING','RUNNING_TOOLS','ALL_AVAILABLE',"
    "'PARTIAL_ALTERNATIVE','NO_FEASIBLE_SCHEDULE','AWAITING_APPROVAL',"
    "'STALE','ERROR','CANCELLED')"
)


def _restore_snapshot_trigger() -> None:
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
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_constraint("ck_agent_runs_status", type_="check")
        batch.create_check_constraint("ck_agent_runs_status", _STATUS_CHECK)
    _restore_snapshot_trigger()


def downgrade() -> None:
    bind = op.get_bind()
    queued_count = bind.scalar(
        sa.text("SELECT count(*) FROM agent_runs WHERE status = 'QUEUED'")
    )
    if queued_count:
        raise RuntimeError(
            "Cannot downgrade while queued Agent runs exist; drain or cancel them first."
        )
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_constraint("ck_agent_runs_status", type_="check")
        batch.create_check_constraint(
            "ck_agent_runs_status",
            "status IN ("
            "'WAITING_FOR_INPUT','ANALYZING','RUNNING_TOOLS','ALL_AVAILABLE',"
            "'PARTIAL_ALTERNATIVE','NO_FEASIBLE_SCHEDULE','AWAITING_APPROVAL',"
            "'STALE','ERROR','CANCELLED')",
        )
    _restore_snapshot_trigger()
