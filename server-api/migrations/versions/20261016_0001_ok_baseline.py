"""Baseline ok_* schema matching database.initialize() versions 1..2.

Revision ID: 20261016_0001
Revises:
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261016_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ok_rooms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("host_id", sa.String(length=36), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dirty", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ok_rooms_code", "ok_rooms", ["code"], unique=True)

    op.create_table(
        "ok_schema_versions",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "ok_members",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("nickname", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("request_key_hash", sa.String(length=64), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["ok_rooms.id"]),
        sa.UniqueConstraint("room_id", "nickname"),
    )
    op.create_index("ix_ok_members_room_id", "ok_members", ["room_id"])
    op.create_index("ix_ok_members_token_hash", "ok_members", ["token_hash"], unique=True)
    op.create_index("ix_ok_members_request_key_hash", "ok_members", ["request_key_hash"], unique=True)

    op.create_table(
        "ok_ai_drafts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column("raw_text", sa.String(length=1500), nullable=False),
        sa.Column("model_output", sa.JSON(), nullable=False),
        sa.Column("app_draft", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["ok_members.id"]),
    )
    op.create_index("ix_ok_ai_drafts_member_id", "ok_ai_drafts", ["member_id"])

    op.create_table(
        "ok_condition_submissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("confirmed", sa.JSON(), nullable=False),
        sa.Column("ai_draft_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["ok_members.id"]),
        sa.ForeignKeyConstraint(["ai_draft_id"], ["ok_ai_drafts.id"]),
        sa.UniqueConstraint("member_id", "version"),
    )
    op.create_index("ix_ok_condition_submissions_member_id", "ok_condition_submissions", ["member_id"])

    op.create_table(
        "ok_proposals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("solver_status", sa.String(length=20), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["ok_rooms.id"]),
        sa.UniqueConstraint("room_id", "round"),
    )
    op.create_index("ix_ok_proposals_room_id", "ok_proposals", ["room_id"])

    op.create_table(
        "ok_consents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("proposal_id", sa.String(length=36), nullable=False),
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["ok_proposals.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["ok_members.id"]),
        sa.UniqueConstraint("proposal_id", "member_id"),
    )
    op.create_index("ix_ok_consents_proposal_id", "ok_consents", ["proposal_id"])
    op.create_index("ix_ok_consents_member_id", "ok_consents", ["member_id"])

    op.create_table(
        "ok_room_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("room_id", sa.String(length=36), nullable=False),
        sa.Column("message", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["ok_rooms.id"]),
    )
    op.create_index("ix_ok_room_events_room_id", "ok_room_events", ["room_id"])

    # Preserve legacy version rows that initialize() used to insert.
    op.execute(
        sa.text(
            "INSERT INTO ok_schema_versions(version, applied_at) VALUES "
            "(1, CURRENT_TIMESTAMP), (2, CURRENT_TIMESTAMP) "
            "ON CONFLICT (version) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_table("ok_room_events")
    op.drop_table("ok_consents")
    op.drop_table("ok_proposals")
    op.drop_table("ok_condition_submissions")
    op.drop_table("ok_ai_drafts")
    op.drop_table("ok_members")
    op.drop_table("ok_schema_versions")
    op.drop_table("ok_rooms")
