"""Add room API compatibility columns for workflow port.

Revision ID: 20261101_0003
Revises: 20261101_0002
Create Date: 2026-11-02

Dialect notes:
- PostgreSQL: DROP CONSTRAINT IF EXISTS, then ADD CONSTRAINT (PG 18 compatible).
- SQLite: batch_alter_table rebuilds the table to change CHECKs.
Failures are not swallowed; unsupported dialects raise.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_0003"
down_revision: Union[str, Sequence[str], None] = "20261101_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOLVER_CHECK = (
    "solver_status IN ("
    "'PENDING','COMPLETED','FAILED',"
    "'OPTIMAL','FEASIBLE','INFEASIBLE','UNBOUNDED','ERROR','idle')"
)
CONSENT_CHECK = (
    "status IN ("
    "'PENDING','AGREED','WITHDRAWN','REJECTED',"
    "'pending','agreed','review')"
)


def _dialect() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column("host_member_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_rooms_host_member_id", "rooms", ["host_member_id"])
    op.add_column(
        "rooms",
        sa.Column(
            "progress_status",
            sa.String(length=20),
            nullable=False,
            server_default="collecting",
        ),
    )
    op.add_column(
        "rooms",
        sa.Column("meeting_settings", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "rooms",
        sa.Column("dirty", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "rooms",
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "idempotency_records",
        sa.Column("payload", sa.JSON(), nullable=True),
    )

    dialect = _dialect()
    if dialect == "postgresql":
        op.execute(sa.text("ALTER TABLE account_sessions DROP CONSTRAINT IF EXISTS ck_account_sessions_expires"))
        op.execute(sa.text("ALTER TABLE proposals DROP CONSTRAINT IF EXISTS ck_proposals_solver_status"))
        op.execute(
            sa.text(f"ALTER TABLE proposals ADD CONSTRAINT ck_proposals_solver_status CHECK ({SOLVER_CHECK})")
        )
        op.execute(sa.text("ALTER TABLE proposal_consents DROP CONSTRAINT IF EXISTS ck_proposal_consents_status"))
        op.execute(
            sa.text(
                f"ALTER TABLE proposal_consents ADD CONSTRAINT ck_proposal_consents_status CHECK ({CONSENT_CHECK})"
            )
        )
    elif dialect == "sqlite":
        with op.batch_alter_table("account_sessions") as batch:
            batch.drop_constraint("ck_account_sessions_expires", type_="check")
        with op.batch_alter_table("proposals") as batch:
            batch.drop_constraint("ck_proposals_solver_status", type_="check")
            batch.create_check_constraint("ck_proposals_solver_status", SOLVER_CHECK)
        with op.batch_alter_table("proposal_consents") as batch:
            batch.drop_constraint("ck_proposal_consents_status", type_="check")
            batch.create_check_constraint("ck_proposal_consents_status", CONSENT_CHECK)
    else:
        raise NotImplementedError(f"migration 20261101_0003 unsupported dialect: {dialect}")


def downgrade() -> None:
    dialect = _dialect()
    if dialect == "postgresql":
        op.execute(sa.text("ALTER TABLE proposals DROP CONSTRAINT IF EXISTS ck_proposals_solver_status"))
        op.execute(
            sa.text(
                "ALTER TABLE proposals ADD CONSTRAINT ck_proposals_solver_status "
                "CHECK (solver_status IN ('PENDING', 'COMPLETED', 'FAILED'))"
            )
        )
        op.execute(sa.text("ALTER TABLE proposal_consents DROP CONSTRAINT IF EXISTS ck_proposal_consents_status"))
        op.execute(
            sa.text(
                "ALTER TABLE proposal_consents ADD CONSTRAINT ck_proposal_consents_status "
                "CHECK (status IN ('PENDING', 'AGREED', 'WITHDRAWN', 'REJECTED'))"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE account_sessions DROP CONSTRAINT IF EXISTS ck_account_sessions_expires"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE account_sessions ADD CONSTRAINT ck_account_sessions_expires "
                "CHECK (expires_at > created_at)"
            )
        )
    elif dialect == "sqlite":
        with op.batch_alter_table("proposals") as batch:
            batch.drop_constraint("ck_proposals_solver_status", type_="check")
            batch.create_check_constraint(
                "ck_proposals_solver_status",
                "solver_status IN ('PENDING', 'COMPLETED', 'FAILED')",
            )
        with op.batch_alter_table("proposal_consents") as batch:
            batch.drop_constraint("ck_proposal_consents_status", type_="check")
            batch.create_check_constraint(
                "ck_proposal_consents_status",
                "status IN ('PENDING', 'AGREED', 'WITHDRAWN', 'REJECTED')",
            )
        with op.batch_alter_table("account_sessions") as batch:
            batch.create_check_constraint(
                "ck_account_sessions_expires",
                "expires_at > created_at",
            )
    else:
        raise NotImplementedError(f"migration 20261101_0003 unsupported dialect: {dialect}")

    op.drop_column("idempotency_records", "payload")
    op.drop_column("rooms", "current_round")
    op.drop_column("rooms", "dirty")
    op.drop_column("rooms", "meeting_settings")
    op.drop_column("rooms", "progress_status")
    op.drop_index("ix_rooms_host_member_id", table_name="rooms")
    op.drop_column("rooms", "host_member_id")
