"""Initial schema v2.1 (19 tables) + admin security extras (3).

Revision ID: 20261101_0001
Revises:
Create Date: 2026-11-01

Empty / new database only. Do not apply to existing ok_* production DB.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261101_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('accounts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('login_email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=512), nullable=False),
    sa.Column('account_type', sa.String(length=20), nullable=False),
    sa.Column('account_status', sa.String(length=20), nullable=False),
    sa.Column('admin_role', sa.String(length=20), nullable=True),
    sa.Column('approved', sa.Boolean(), nullable=False),
    sa.Column('failures', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("account_status IN ('ACTIVE', 'DISABLED', 'FROZEN')", name='ck_accounts_account_status'),
    sa.CheckConstraint("account_type IN ('USER', 'ADMIN')", name='ck_accounts_account_type'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accounts_login_email'), 'accounts', ['login_email'], unique=True)
    op.create_table('admin_rate_limits',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('reset', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_admin_rate_limits_reset'), 'admin_rate_limits', ['reset'], unique=False)
    op.create_table('account_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('csrf', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('expires_at > created_at', name='ck_account_sessions_expires'),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_account_sessions_account_id'), 'account_sessions', ['account_id'], unique=False)
    op.create_index(op.f('ix_account_sessions_token_hash'), 'account_sessions', ['token_hash'], unique=True)
    op.create_table('admin_audit_logs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('admin_account_id', sa.String(length=36), nullable=True),
    sa.Column('action_type', sa.String(length=50), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.String(length=64), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['admin_account_id'], ['accounts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_logs_admin_account_id'), 'admin_audit_logs', ['admin_account_id'], unique=False)
    op.create_index(op.f('ix_admin_audit_logs_occurred_at'), 'admin_audit_logs', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_admin_audit_logs_target_id'), 'admin_audit_logs', ['target_id'], unique=False)
    op.create_index(op.f('ix_admin_audit_logs_target_type'), 'admin_audit_logs', ['target_type'], unique=False)
    op.create_table('admin_otps',
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('challenge', sa.String(length=64), nullable=False),
    sa.Column('digest', sa.String(length=64), nullable=False),
    sa.Column('expires', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('account_id'),
    sa.UniqueConstraint('challenge')
    )
    op.create_table('announcements',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_by_admin_id', sa.String(length=36), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('audience', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')", name='ck_announcements_status'),
    sa.ForeignKeyConstraint(['created_by_admin_id'], ['accounts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('expires_at > created_at', name='ck_password_reset_tokens_expires'),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_account_id'), 'password_reset_tokens', ['account_id'], unique=False)
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_table('rooms',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=8), nullable=False),
    sa.Column('created_by_account_id', sa.String(length=36), nullable=True),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('lifecycle_status', sa.String(length=40), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("lifecycle_status IN ('COLLECTING_CONDITIONS','READY_FOR_ASSIGNMENT','WAITING_FOR_CONSENT','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED')", name='ck_rooms_lifecycle_status'),
    sa.CheckConstraint('ends_at > starts_at', name='ck_rooms_time_range'),
    sa.ForeignKeyConstraint(['created_by_account_id'], ['accounts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rooms_code'), 'rooms', ['code'], unique=True)
    op.create_index(op.f('ix_rooms_created_by_account_id'), 'rooms', ['created_by_account_id'], unique=False)
    op.create_table('service_controls',
    sa.Column('feature_key', sa.String(length=64), nullable=False),
    sa.Column('control_status', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('updated_by_admin_id', sa.String(length=36), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("control_status IN ('ENABLED', 'DISABLED', 'READ_ONLY')", name='ck_service_controls_status'),
    sa.ForeignKeyConstraint(['updated_by_admin_id'], ['accounts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('feature_key')
    )
    op.create_table('room_controls',
    sa.Column('room_id', sa.String(length=36), nullable=False),
    sa.Column('control_status', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('updated_by_admin_id', sa.String(length=36), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("control_status IN ('ACTIVE', 'SUSPENDED')", name='ck_room_controls_status'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_admin_id'], ['accounts.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('room_id')
    )
    op.create_table('room_cycle_archives',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('room_id', sa.String(length=36), nullable=False),
    sa.Column('cycle', sa.Integer(), nullable=False),
    sa.Column('request_key', sa.String(length=100), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('room_id', 'cycle', name='uq_room_cycle_archives_room_cycle'),
    sa.UniqueConstraint('room_id', 'request_key', name='uq_room_cycle_archives_room_request')
    )
    op.create_index(op.f('ix_room_cycle_archives_room_id'), 'room_cycle_archives', ['room_id'], unique=False)
    op.create_table('room_members',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('room_id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('nickname', sa.String(length=30), nullable=False),
    sa.Column('room_role', sa.String(length=20), nullable=False),
    sa.Column('membership_status', sa.String(length=20), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("membership_status IN ('ACTIVE', 'LEFT', 'REMOVED')", name='ck_room_members_membership_status'),
    sa.CheckConstraint("room_role IN ('OWNER', 'MEMBER')", name='ck_room_members_room_role'),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('room_id', 'account_id', name='uq_room_members_room_account'),
    sa.UniqueConstraint('room_id', 'nickname', name='uq_room_members_room_nickname')
    )
    op.create_index(op.f('ix_room_members_account_id'), 'room_members', ['account_id'], unique=False)
    op.create_index(op.f('ix_room_members_room_id'), 'room_members', ['room_id'], unique=False)
    op.create_table('room_roles',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('room_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=30), nullable=False),
    sa.Column('required_count', sa.Integer(), nullable=False),
    sa.CheckConstraint('required_count > 0', name='ck_room_roles_required_count'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('room_id', 'name', name='uq_room_roles_room_name')
    )
    op.create_index(op.f('ix_room_roles_room_id'), 'room_roles', ['room_id'], unique=False)
    op.create_table('ai_drafts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('room_member_id', sa.String(length=36), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('parse_status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("parse_status IN ('PENDING', 'COMPLETED', 'FAILED')", name='ck_ai_drafts_parse_status'),
    sa.ForeignKeyConstraint(['room_member_id'], ['room_members.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_drafts_room_member_id'), 'ai_drafts', ['room_member_id'], unique=False)
    op.create_table('proposals',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('room_id', sa.String(length=36), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('source_revision', sa.Integer(), nullable=False),
    sa.Column('solver_status', sa.String(length=20), nullable=False),
    sa.Column('proposal_status', sa.String(length=40), nullable=False),
    sa.Column('created_by_member_id', sa.String(length=36), nullable=True),
    sa.Column('finalized_by_member_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('invalidated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("proposal_status IN ('PROPOSED','WAITING_FOR_CONSENT','CONFIRMED','INVALIDATED','REJECTED')", name='ck_proposals_proposal_status'),
    sa.CheckConstraint("solver_status IN ('PENDING', 'COMPLETED', 'FAILED')", name='ck_proposals_solver_status'),
    sa.ForeignKeyConstraint(['created_by_member_id'], ['room_members.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['finalized_by_member_id'], ['room_members.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('room_id', 'round', name='uq_proposals_room_round')
    )
    op.create_index(op.f('ix_proposals_room_id'), 'proposals', ['room_id'], unique=False)
    op.create_table('room_events',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('room_id', sa.String(length=36), nullable=False),
    sa.Column('actor_member_id', sa.String(length=36), nullable=True),
    sa.Column('event_type', sa.String(length=40), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_member_id'], ['room_members.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_room_events_room_id'), 'room_events', ['room_id'], unique=False)
    op.create_table('condition_submissions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('room_member_id', sa.String(length=36), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('ai_draft_id', sa.String(length=36), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['ai_draft_id'], ['ai_drafts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['room_member_id'], ['room_members.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('room_member_id', 'version', name='uq_condition_submissions_member_version')
    )
    op.create_index(op.f('ix_condition_submissions_room_member_id'), 'condition_submissions', ['room_member_id'], unique=False)
    op.create_table('proposal_assignments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('room_member_id', sa.String(length=36), nullable=False),
    sa.Column('room_role_id', sa.String(length=36), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('ends_at > starts_at', name='ck_proposal_assignments_time_range'),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_member_id'], ['room_members.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_role_id'], ['room_roles.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_proposal_assignments_proposal_id'), 'proposal_assignments', ['proposal_id'], unique=False)
    op.create_index(op.f('ix_proposal_assignments_room_member_id'), 'proposal_assignments', ['room_member_id'], unique=False)
    op.create_index(op.f('ix_proposal_assignments_room_role_id'), 'proposal_assignments', ['room_role_id'], unique=False)
    op.create_table('proposal_consents',
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('room_member_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('PENDING', 'AGREED', 'WITHDRAWN', 'REJECTED')", name='ck_proposal_consents_status'),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_member_id'], ['room_members.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('proposal_id', 'room_member_id')
    )
    op.create_table('condition_available_slots',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('condition_submission_id', sa.String(length=36), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('ends_at > starts_at', name='ck_condition_available_slots_range'),
    sa.ForeignKeyConstraint(['condition_submission_id'], ['condition_submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_condition_available_slots_condition_submission_id'), 'condition_available_slots', ['condition_submission_id'], unique=False)
    op.create_table('condition_role_preferences',
    sa.Column('condition_submission_id', sa.String(length=36), nullable=False),
    sa.Column('room_role_id', sa.String(length=36), nullable=False),
    sa.Column('preference', sa.String(length=20), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.CheckConstraint("preference IN ('PREFERRED', 'AVAILABLE', 'AVOID')", name='ck_condition_role_preferences_preference'),
    sa.ForeignKeyConstraint(['condition_submission_id'], ['condition_submissions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_role_id'], ['room_roles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('condition_submission_id', 'room_role_id')
    )
    op.create_table('proposal_condition_inputs',
    sa.Column('proposal_id', sa.String(length=36), nullable=False),
    sa.Column('room_member_id', sa.String(length=36), nullable=False),
    sa.Column('condition_submission_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['condition_submission_id'], ['condition_submissions.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_member_id'], ['room_members.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('proposal_id', 'room_member_id'),
    sa.UniqueConstraint('proposal_id', 'room_member_id', name='uq_proposal_condition_inputs_proposal_member')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('proposal_condition_inputs')
    op.drop_table('condition_role_preferences')
    op.drop_index(op.f('ix_condition_available_slots_condition_submission_id'), table_name='condition_available_slots')
    op.drop_table('condition_available_slots')
    op.drop_table('proposal_consents')
    op.drop_index(op.f('ix_proposal_assignments_room_role_id'), table_name='proposal_assignments')
    op.drop_index(op.f('ix_proposal_assignments_room_member_id'), table_name='proposal_assignments')
    op.drop_index(op.f('ix_proposal_assignments_proposal_id'), table_name='proposal_assignments')
    op.drop_table('proposal_assignments')
    op.drop_index(op.f('ix_condition_submissions_room_member_id'), table_name='condition_submissions')
    op.drop_table('condition_submissions')
    op.drop_index(op.f('ix_room_events_room_id'), table_name='room_events')
    op.drop_table('room_events')
    op.drop_index(op.f('ix_proposals_room_id'), table_name='proposals')
    op.drop_table('proposals')
    op.drop_index(op.f('ix_ai_drafts_room_member_id'), table_name='ai_drafts')
    op.drop_table('ai_drafts')
    op.drop_index(op.f('ix_room_roles_room_id'), table_name='room_roles')
    op.drop_table('room_roles')
    op.drop_index(op.f('ix_room_members_room_id'), table_name='room_members')
    op.drop_index(op.f('ix_room_members_account_id'), table_name='room_members')
    op.drop_table('room_members')
    op.drop_index(op.f('ix_room_cycle_archives_room_id'), table_name='room_cycle_archives')
    op.drop_table('room_cycle_archives')
    op.drop_table('room_controls')
    op.drop_table('service_controls')
    op.drop_index(op.f('ix_rooms_created_by_account_id'), table_name='rooms')
    op.drop_index(op.f('ix_rooms_code'), table_name='rooms')
    op.drop_table('rooms')
    op.drop_index(op.f('ix_password_reset_tokens_token_hash'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_account_id'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_table('announcements')
    op.drop_table('admin_otps')
    op.drop_index(op.f('ix_admin_audit_logs_target_type'), table_name='admin_audit_logs')
    op.drop_index(op.f('ix_admin_audit_logs_target_id'), table_name='admin_audit_logs')
    op.drop_index(op.f('ix_admin_audit_logs_occurred_at'), table_name='admin_audit_logs')
    op.drop_index(op.f('ix_admin_audit_logs_admin_account_id'), table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
    op.drop_index(op.f('ix_account_sessions_token_hash'), table_name='account_sessions')
    op.drop_index(op.f('ix_account_sessions_account_id'), table_name='account_sessions')
    op.drop_table('account_sessions')
    op.drop_index(op.f('ix_admin_rate_limits_reset'), table_name='admin_rate_limits')
    op.drop_table('admin_rate_limits')
    op.drop_index(op.f('ix_accounts_login_email'), table_name='accounts')
    op.drop_table('accounts')

