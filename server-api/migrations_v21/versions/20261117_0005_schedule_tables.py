"""Add Potato Meet schedule_* + notification tables (additive only).

Revision ID: 20261117_0005
Revises: 20261101_0004
Create Date: 2026-11-17

- Creates schedule_* coordination tables and push/notification helpers.
- Does NOT drop or alter existing condition_*/proposals* tables.
- SSE DB outbox (scheduling_events) is intentionally omitted.
- Apply only to empty/dev DB after local review; not for production in this draft step.

Note on uq_proposal_condition_inputs_proposal_member:
  Declared in 20261101_0001 with the composite PK. On PostgreSQL the name is
  attached to the PRIMARY KEY (contype=p); a separate UNIQUE is not created.
  Re-adding it in 0005 causes DuplicateTable. Do not recreate here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261117_0005"
down_revision: Union[str, Sequence[str], None] = "20261101_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedule_collections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("hints_enabled", sa.Boolean(), nullable=False),
        sa.Column("scope_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_reason", sa.String(length=20), nullable=True),
        sa.Column("extended_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("cycle BETWEEN 0 AND 4", name="ck_schedule_collections_cycle"),
        sa.CheckConstraint("kind IN ('NORMAL', 'READJUST')", name="ck_schedule_collections_kind"),
        sa.CheckConstraint(
            "scope_ends_at > scope_starts_at", name="ck_schedule_collections_scope"
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED')", name="ck_schedule_collections_status"
        ),
        sa.CheckConstraint(
            "closed_reason IS NULL OR closed_reason IN ('ALL_DONE', 'DEADLINE')",
            name="ck_schedule_collections_closed_reason",
        ),
        sa.CheckConstraint(
            "extended_count BETWEEN 0 AND 1",
            name="ck_schedule_collections_extended_count",
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "room_id", "cycle", name="uq_schedule_collections_room_cycle"
        ),
    )
    op.create_index(
        op.f("ix_schedule_collections_room_id"),
        "schedule_collections",
        ["room_id"],
        unique=False,
    )
    op.create_index(
        "uq_schedule_collections_open_room",
        "schedule_collections",
        ["room_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
        sqlite_where=sa.text("status = 'OPEN'"),
    )

    op.create_table(
        "schedule_responses",
        sa.Column("collection_id", sa.String(length=36), nullable=False),
        sa.Column("room_member_id", sa.String(length=36), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["schedule_collections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["room_member_id"], ["room_members.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("collection_id", "room_member_id"),
    )

    op.create_table(
        "schedule_response_ranges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("collection_id", sa.String(length=36), nullable=False),
        sa.Column("room_member_id", sa.String(length=36), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ends_at > starts_at", name="ck_schedule_response_ranges_range"
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["schedule_collections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["room_member_id"], ["room_members.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_response_ranges_collection_id"),
        "schedule_response_ranges",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_response_ranges_room_member_id"),
        "schedule_response_ranges",
        ["room_member_id"],
        unique=False,
    )

    op.create_table(
        "schedule_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("collection_id", sa.String(length=36), nullable=True),
        sa.Column("max_count", sa.Integer(), nullable=False),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("voter_count", sa.Integer(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("voting_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voting_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("excluded_soon_count", sa.Integer(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_reason", sa.String(length=20), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "closed_reason IS NULL OR closed_reason IN ('ALL_VOTED', 'TIMEOUT')",
            name="ck_schedule_runs_closed_reason",
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["schedule_collections.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_member_id"], ["room_members.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_runs_room_id"), "schedule_runs", ["room_id"], unique=False
    )

    op.create_table(
        "schedule_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_count", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_schedule_candidates_range"),
        sa.CheckConstraint(
            "available_count >= 2", name="ck_schedule_candidates_available_count"
        ),
        sa.CheckConstraint("sort_order > 0", name="ck_schedule_candidates_sort_order"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["schedule_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "sort_order", name="uq_schedule_candidates_run_sort"
        ),
    )
    op.create_index(
        op.f("ix_schedule_candidates_run_id"),
        "schedule_candidates",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_candidates_room_id"),
        "schedule_candidates",
        ["room_id"],
        unique=False,
    )

    op.create_table(
        "schedule_candidate_members",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("room_member_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["schedule_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["room_member_id"], ["room_members.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("candidate_id", "room_member_id"),
    )

    op.create_table(
        "schedule_votes",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("room_member_id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["schedule_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["room_member_id"], ["room_members.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("candidate_id", "room_member_id"),
    )
    op.create_index(
        op.f("ix_schedule_votes_room_id"), "schedule_votes", ["room_id"], unique=False
    )

    op.create_table(
        "schedule_vote_ballots",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("room_member_id", sa.String(length=36), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["schedule_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["room_member_id"], ["room_members.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", "room_member_id"),
    )

    op.create_table(
        "schedule_results",
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("vote_count", sa.Integer(), nullable=True),
        sa.Column("tie_broken", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "method IN ('AUTO', 'VOTE')", name="ck_schedule_results_method"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["schedule_candidates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("room_id"),
    )

    op.create_table(
        "push_devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("platform", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "platform IN ('ANDROID')", name="ck_push_devices_platform"
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_push_devices_account_id"), "push_devices", ["account_id"], unique=False
    )

    op.create_table(
        "notification_settings",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("start_enabled", sa.Boolean(), nullable=False),
        sa.Column("remind_enabled", sa.Boolean(), nullable=False),
        sa.Column("extend_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )

    op.create_table(
        "notification_log",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("event_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('START', 'REMIND', 'EXTEND')", name="ck_notification_log_kind"
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'SENT', 'FAILED', 'SKIPPED')",
            name="ck_notification_log_status",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "room_id",
            "kind",
            "event_key",
            "account_id",
            name="uq_notification_log_dedupe",
        ),
    )
    op.create_index(
        op.f("ix_notification_log_room_id"),
        "notification_log",
        ["room_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop only tables introduced by this revision (additive rollback)."""
    op.drop_index(op.f("ix_notification_log_room_id"), table_name="notification_log")
    op.drop_table("notification_log")
    op.drop_table("notification_settings")
    op.drop_index(op.f("ix_push_devices_account_id"), table_name="push_devices")
    op.drop_table("push_devices")
    op.drop_table("schedule_results")
    op.drop_table("schedule_vote_ballots")
    op.drop_index(op.f("ix_schedule_votes_room_id"), table_name="schedule_votes")
    op.drop_table("schedule_votes")
    op.drop_table("schedule_candidate_members")
    op.drop_index(
        op.f("ix_schedule_candidates_room_id"), table_name="schedule_candidates"
    )
    op.drop_index(op.f("ix_schedule_candidates_run_id"), table_name="schedule_candidates")
    op.drop_table("schedule_candidates")
    op.drop_index(op.f("ix_schedule_runs_room_id"), table_name="schedule_runs")
    op.drop_table("schedule_runs")
    op.drop_index(
        op.f("ix_schedule_response_ranges_room_member_id"),
        table_name="schedule_response_ranges",
    )
    op.drop_index(
        op.f("ix_schedule_response_ranges_collection_id"),
        table_name="schedule_response_ranges",
    )
    op.drop_table("schedule_response_ranges")
    op.drop_table("schedule_responses")
    op.drop_index(
        "uq_schedule_collections_open_room", table_name="schedule_collections"
    )
    op.drop_index(
        op.f("ix_schedule_collections_room_id"), table_name="schedule_collections"
    )
    op.drop_table("schedule_collections")
