"""Additive Agent Core persistence for v2.1.

Revision ID: 20261102_0005
Revises: 20261101_0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261102_0005"
down_revision: Union[str, Sequence[str], None] = "20261101_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dialect() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column(
            "agent_input_revision",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    with op.batch_alter_table("rooms") as batch:
        batch.create_check_constraint(
            "ck_rooms_agent_input_revision", "agent_input_revision >= 1"
        )

    op.create_table(
        "room_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("invited_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("invitation_status", sa.String(length=20), nullable=False),
        sa.Column("response_status", sa.String(length=20), nullable=False),
        sa.Column("eligibility_status", sa.String(length=24), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("excluded_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "invitation_status IN ('NOT_SENT', 'SENT')",
            name="ck_room_invitations_invitation_status",
        ),
        sa.CheckConstraint(
            "response_status IN ('PENDING', 'ACCEPTED', 'DECLINED')",
            name="ck_room_invitations_response_status",
        ),
        sa.CheckConstraint(
            "eligibility_status IN ('ACTIVE', 'EXCLUDED_BY_HOST')",
            name="ck_room_invitations_eligibility_status",
        ),
        sa.CheckConstraint(
            "(invitation_status = 'SENT' AND invited_at IS NOT NULL) OR "
            "(invitation_status = 'NOT_SENT' AND invited_at IS NULL)",
            name="ck_room_invitations_sent_timestamp",
        ),
        sa.CheckConstraint(
            "response_status = 'PENDING' OR invitation_status = 'SENT'",
            name="ck_room_invitations_response_requires_sent",
        ),
        sa.CheckConstraint(
            "(eligibility_status = 'ACTIVE' AND excluded_at IS NULL "
            "AND exclusion_reason IS NULL) OR "
            "(eligibility_status = 'EXCLUDED_BY_HOST' "
            "AND invitation_status = 'SENT' AND response_status = 'PENDING' "
            "AND excluded_at IS NOT NULL AND exclusion_reason IS NOT NULL)",
            name="ck_room_invitations_exclusion_state",
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["invited_by_member_id"], ["room_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["excluded_by_member_id"], ["room_members.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "room_id", "account_id", name="uq_room_invitations_room_account"
        ),
    )
    op.create_index("ix_room_invitations_room_id", "room_invitations", ["room_id"])
    op.create_index("ix_room_invitations_account_id", "room_invitations", ["account_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_session_id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("input_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("consent_round", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approval_status", sa.String(length=20), nullable=False),
        sa.Column("selected_candidate_id", sa.String(length=36), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("approval_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("retry_of_run_id", sa.String(length=36), nullable=True),
        sa.Column("checkpoint_thread_id", sa.String(length=128), nullable=True),
        sa.Column("checkpoint_ref", sa.String(length=256), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("lease_token_hash", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ("
            "'WAITING_FOR_INPUT','ANALYZING','RUNNING_TOOLS','ALL_AVAILABLE',"
            "'PARTIAL_ALTERNATIVE','NO_FEASIBLE_SCHEDULE','AWAITING_APPROVAL',"
            "'STALE','ERROR','CANCELLED')",
            name="ck_agent_runs_status",
        ),
        sa.CheckConstraint(
            "approval_status IN "
            "('NOT_REQUESTED','PENDING','APPROVED','REJECTED','SUPERSEDED')",
            name="ck_agent_runs_approval_status",
        ),
        sa.CheckConstraint("source_revision >= 1", name="ck_agent_runs_source_revision"),
        sa.CheckConstraint("consent_round >= 1", name="ck_agent_runs_consent_round"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_agent_runs_attempt_number"),
        sa.CheckConstraint(
            "length(input_snapshot_hash) = 64",
            name="ck_agent_runs_snapshot_hash_length",
        ),
        sa.CheckConstraint(
            "retry_of_run_id IS NULL OR retry_of_run_id != id",
            name="ck_agent_runs_retry_not_self",
        ),
        sa.CheckConstraint(
            "(worker_id IS NULL AND lease_token_hash IS NULL AND lease_expires_at IS NULL) "
            "OR (worker_id IS NOT NULL AND lease_token_hash IS NOT NULL "
            "AND lease_expires_at IS NOT NULL)",
            name="ck_agent_runs_lease_fields",
        ),
        sa.CheckConstraint(
            "(selected_candidate_id IS NULL AND selected_at IS NULL) OR "
            "(selected_candidate_id IS NOT NULL AND selected_at IS NOT NULL)",
            name="ck_agent_runs_selection_fields",
        ),
        sa.CheckConstraint(
            "(approval_status NOT IN ('APPROVED','REJECTED') "
            "AND approval_by_member_id IS NULL AND approval_at IS NULL) OR "
            "(approval_status IN ('APPROVED','REJECTED') "
            "AND approval_by_member_id IS NOT NULL AND approval_at IS NOT NULL)",
            name="ck_agent_runs_approval_fields",
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_member_id"], ["room_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["approval_by_member_id"], ["room_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["retry_of_run_id"], ["agent_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_agent_session_id", "agent_runs", ["agent_session_id"])
    op.create_index("ix_agent_runs_room_id", "agent_runs", ["room_id"])

    op.create_table(
        "agent_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_zone", sa.String(length=32), nullable=False),
        sa.Column("candidate_type", sa.String(length=24), nullable=False),
        sa.Column("solver_status", sa.String(length=16), nullable=False),
        sa.Column("maximum_attendees_proven", sa.Boolean(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rank BETWEEN 1 AND 3", name="ck_agent_candidates_top_three"),
        sa.CheckConstraint(
            "candidate_type IN ('ALL_AVAILABLE','PARTIAL_ALTERNATIVE')",
            name="ck_agent_candidates_type",
        ),
        sa.CheckConstraint(
            "solver_status IN ('OPTIMAL','FEASIBLE')",
            name="ck_agent_candidates_solver_status",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_agent_candidates_time_range"),
        sa.CheckConstraint(
            "time_zone = 'Asia/Seoul'", name="ck_agent_candidates_time_zone"
        ),
        sa.CheckConstraint("source_revision >= 1", name="ck_agent_candidates_source_revision"),
        sa.CheckConstraint(
            "length(source_snapshot_hash) = 64",
            name="ck_agent_candidates_snapshot_hash_length",
        ),
        sa.CheckConstraint(
            "verified IN (FALSE, TRUE)", name="ck_agent_candidates_verified"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "rank", name="uq_agent_candidates_run_rank"),
    )
    op.create_index("ix_agent_candidates_run_id", "agent_candidates", ["run_id"])

    op.create_table(
        "agent_candidate_members",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("room_member_id", sa.String(length=36), nullable=False),
        sa.Column("consent_round", sa.Integer(), nullable=False),
        sa.Column("participation_status", sa.String(length=16), nullable=False),
        sa.Column("consent_status", sa.String(length=12), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "participation_status IN ('ATTENDING','UNAVAILABLE')",
            name="ck_agent_candidate_members_participation",
        ),
        sa.CheckConstraint(
            "consent_status IS NULL OR consent_status IN ('AGREE','DISAGREE')",
            name="ck_agent_candidate_members_consent",
        ),
        sa.CheckConstraint("consent_round >= 1", name="ck_agent_candidate_members_round"),
        sa.CheckConstraint(
            "(consent_status IS NULL AND consented_at IS NULL) OR "
            "(consent_status IS NOT NULL AND consented_at IS NOT NULL "
            "AND participation_status = 'ATTENDING')",
            name="ck_agent_candidate_members_consent_state",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["agent_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["room_member_id"], ["room_members.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("candidate_id", "room_member_id", "consent_round"),
    )

    dialect = _dialect()
    if dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER trg_agent_candidate_consent_immutable
            BEFORE UPDATE OF consent_status, consented_at
            ON agent_candidate_members
            WHEN OLD.consent_status IS NOT NULL
            BEGIN
              SELECT RAISE(ABORT, 'recorded agent consent is immutable');
            END
            """
        )
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
    elif dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_agent_consent_overwrite() RETURNS trigger AS $$
            BEGIN
              IF OLD.consent_status IS NOT NULL THEN
                RAISE EXCEPTION 'recorded agent consent is immutable';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE FUNCTION reject_agent_run_snapshot_change() RETURNS trigger AS $$
            BEGIN
              IF NEW.source_revision IS DISTINCT FROM OLD.source_revision
                OR NEW.input_snapshot_hash IS DISTINCT FROM OLD.input_snapshot_hash
                OR NEW.input_snapshot::text IS DISTINCT FROM OLD.input_snapshot::text THEN
                RAISE EXCEPTION 'agent run snapshot is immutable';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_agent_candidate_consent_immutable
            BEFORE UPDATE OF consent_status, consented_at
            ON agent_candidate_members
            FOR EACH ROW EXECUTE FUNCTION reject_agent_consent_overwrite()
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_agent_run_snapshot_immutable
            BEFORE UPDATE OF source_revision, input_snapshot_hash, input_snapshot
            ON agent_runs
            FOR EACH ROW EXECUTE FUNCTION reject_agent_run_snapshot_change()
            """
        )
    else:
        raise NotImplementedError(
            f"migration 20261102_0005 unsupported dialect: {dialect}"
        )


def downgrade() -> None:
    dialect = _dialect()
    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_agent_candidate_consent_immutable")
        op.execute("DROP TRIGGER IF EXISTS trg_agent_run_snapshot_immutable")
    elif dialect == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_agent_candidate_consent_immutable "
            "ON agent_candidate_members"
        )
        op.execute("DROP FUNCTION IF EXISTS reject_agent_consent_overwrite()")
        op.execute(
            "DROP TRIGGER IF EXISTS trg_agent_run_snapshot_immutable ON agent_runs"
        )
        op.execute("DROP FUNCTION IF EXISTS reject_agent_run_snapshot_change()")
    else:
        raise NotImplementedError(
            f"migration 20261102_0005 unsupported dialect: {dialect}"
        )

    op.drop_table("agent_candidate_members")
    op.drop_index("ix_agent_candidates_run_id", table_name="agent_candidates")
    op.drop_table("agent_candidates")
    op.drop_index("ix_agent_runs_room_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_session_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_room_invitations_account_id", table_name="room_invitations")
    op.drop_index("ix_room_invitations_room_id", table_name="room_invitations")
    op.drop_table("room_invitations")
    with op.batch_alter_table("rooms") as batch:
        batch.drop_constraint("ck_rooms_agent_input_revision", type_="check")
        batch.drop_column("agent_input_revision")
