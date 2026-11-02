"""Agent invitations, durable runs, candidates, and per-round attendance consent."""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class RoomInvitation(Base):
    __tablename__ = "room_invitations"
    __table_args__ = (
        UniqueConstraint("room_id", "account_id", name="uq_room_invitations_room_account"),
        CheckConstraint(
            "invitation_status IN ('NOT_SENT', 'SENT')",
            name="ck_room_invitations_invitation_status",
        ),
        CheckConstraint(
            "response_status IN ('PENDING', 'ACCEPTED', 'DECLINED')",
            name="ck_room_invitations_response_status",
        ),
        CheckConstraint(
            "eligibility_status IN ('ACTIVE', 'EXCLUDED_BY_HOST')",
            name="ck_room_invitations_eligibility_status",
        ),
        CheckConstraint(
            "(invitation_status = 'SENT' AND invited_at IS NOT NULL) OR "
            "(invitation_status = 'NOT_SENT' AND invited_at IS NULL)",
            name="ck_room_invitations_sent_timestamp",
        ),
        CheckConstraint(
            "response_status = 'PENDING' OR invitation_status = 'SENT'",
            name="ck_room_invitations_response_requires_sent",
        ),
        CheckConstraint(
            "(eligibility_status = 'ACTIVE' AND excluded_at IS NULL "
            "AND exclusion_reason IS NULL) OR "
            "(eligibility_status = 'EXCLUDED_BY_HOST' "
            "AND invitation_status = 'SENT' AND response_status = 'PENDING' "
            "AND excluded_at IS NOT NULL AND exclusion_reason IS NOT NULL)",
            name="ck_room_invitations_exclusion_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    invited_by_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    invitation_status: Mapped[str] = mapped_column(String(20), default="NOT_SENT")
    response_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    eligibility_status: Mapped[str] = mapped_column(String(24), default="ACTIVE")
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    excluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    excluded_by_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'QUEUED','RUNNING','WAITING_FOR_INPUT','ANALYZING','RUNNING_TOOLS','ALL_AVAILABLE',"
            "'PARTIAL_ALTERNATIVE','NO_FEASIBLE_SCHEDULE','AWAITING_APPROVAL',"
            "'STALE','ERROR','FAILED','CANCELLED')",
            name="ck_agent_runs_status",
        ),
        CheckConstraint(
            "approval_status IN "
            "('NOT_REQUESTED','PENDING','APPROVED','REJECTED','SUPERSEDED')",
            name="ck_agent_runs_approval_status",
        ),
        CheckConstraint("source_revision >= 1", name="ck_agent_runs_source_revision"),
        CheckConstraint("consent_round >= 1", name="ck_agent_runs_consent_round"),
        CheckConstraint("attempt_number >= 1", name="ck_agent_runs_attempt_number"),
        CheckConstraint(
            "length(input_snapshot_hash) = 64",
            name="ck_agent_runs_snapshot_hash_length",
        ),
        CheckConstraint(
            "retry_of_run_id IS NULL OR retry_of_run_id != id",
            name="ck_agent_runs_retry_not_self",
        ),
        CheckConstraint(
            "(worker_id IS NULL AND lease_token_hash IS NULL AND lease_expires_at IS NULL) "
            "OR (worker_id IS NOT NULL AND lease_token_hash IS NOT NULL "
            "AND lease_expires_at IS NOT NULL)",
            name="ck_agent_runs_lease_fields",
        ),
        CheckConstraint(
            "(selected_candidate_id IS NULL AND selected_at IS NULL) OR "
            "(selected_candidate_id IS NOT NULL AND selected_at IS NOT NULL)",
            name="ck_agent_runs_selection_fields",
        ),
        CheckConstraint(
            "(approval_status NOT IN ('APPROVED','REJECTED') "
            "AND approval_by_member_id IS NULL AND approval_at IS NULL) OR "
            "(approval_status IN ('APPROVED','REJECTED') "
            "AND approval_by_member_id IS NOT NULL AND approval_at IS NOT NULL)",
            name="ck_agent_runs_approval_fields",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    agent_session_id: Mapped[str] = mapped_column(String(36), index=True)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    created_by_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    source_revision: Mapped[int] = mapped_column(Integer)
    input_snapshot_hash: Mapped[str] = mapped_column(String(64))
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    consent_round: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    approval_status: Mapped[str] = mapped_column(String(20), default="NOT_REQUESTED")
    selected_candidate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_by_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    approval_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    retry_of_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    checkpoint_thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checkpoint_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class AgentCandidate(Base):
    __tablename__ = "agent_candidates"
    __table_args__ = (
        UniqueConstraint("run_id", "rank", name="uq_agent_candidates_run_rank"),
        CheckConstraint("rank BETWEEN 1 AND 3", name="ck_agent_candidates_top_three"),
        CheckConstraint(
            "candidate_type IN ('ALL_AVAILABLE','PARTIAL_ALTERNATIVE')",
            name="ck_agent_candidates_type",
        ),
        CheckConstraint(
            "solver_status IN ('OPTIMAL','FEASIBLE')",
            name="ck_agent_candidates_solver_status",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_agent_candidates_time_range"),
        CheckConstraint(
            "time_zone = 'Asia/Seoul'", name="ck_agent_candidates_time_zone"
        ),
        CheckConstraint("source_revision >= 1", name="ck_agent_candidates_source_revision"),
        CheckConstraint(
            "length(source_snapshot_hash) = 64",
            name="ck_agent_candidates_snapshot_hash_length",
        ),
        CheckConstraint(
            "verified IN (FALSE, TRUE)", name="ck_agent_candidates_verified"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)
    source_snapshot_hash: Mapped[str] = mapped_column(String(64))
    meeting_date: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    time_zone: Mapped[str] = mapped_column(String(32), default="Asia/Seoul")
    candidate_type: Mapped[str] = mapped_column(String(24))
    solver_status: Mapped[str] = mapped_column(String(16))
    maximum_attendees_proven: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AgentCandidateMember(Base):
    __tablename__ = "agent_candidate_members"
    __table_args__ = (
        CheckConstraint(
            "participation_status IN ('ATTENDING','UNAVAILABLE')",
            name="ck_agent_candidate_members_participation",
        ),
        CheckConstraint(
            "consent_status IS NULL OR consent_status IN ('AGREE','DISAGREE')",
            name="ck_agent_candidate_members_consent",
        ),
        CheckConstraint("consent_round >= 1", name="ck_agent_candidate_members_round"),
        CheckConstraint(
            "(consent_status IS NULL AND consented_at IS NULL) OR "
            "(consent_status IS NOT NULL AND consented_at IS NOT NULL "
            "AND participation_status = 'ATTENDING')",
            name="ck_agent_candidate_members_consent_state",
        ),
    )

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("agent_candidates.id", ondelete="CASCADE"), primary_key=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), primary_key=True
    )
    consent_round: Mapped[int] = mapped_column(Integer, primary_key=True)
    participation_status: Mapped[str] = mapped_column(String(16))
    consent_status: Mapped[str | None] = mapped_column(String(12), nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_note: Mapped[str | None] = mapped_column(Text, nullable=True)
