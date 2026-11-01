<<<<<<< HEAD
"""Proposals, condition inputs, assignments, consents."""
from datetime import datetime

from sqlalchemy import (
=======
"""Proposals with JSON snapshots + normalized inputs/assignments/consents.

Storage rule:
- `input_snapshot` / `plan` preserve the exact solver input/output for audit and replay.
- `proposal_condition_inputs` / `proposal_assignments` are the relational view used for
  queries and integrity. They MUST match the same write that produced the JSON.
- Re-assignment increments `round` (UNIQUE per room). Prior rows stay; mark old proposals
  INVALIDATED instead of deleting.
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db_v21.base import Base, now, uid


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        UniqueConstraint("room_id", "round", name="uq_proposals_room_round"),
        CheckConstraint(
<<<<<<< HEAD
            "solver_status IN ('PENDING', 'COMPLETED', 'FAILED')",
=======
            "solver_status IN ("
            "'PENDING','COMPLETED','FAILED',"
            "'OPTIMAL','FEASIBLE','INFEASIBLE','UNBOUNDED','ERROR','idle')",
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
            name="ck_proposals_solver_status",
        ),
        CheckConstraint(
            "proposal_status IN ("
            "'PROPOSED','WAITING_FOR_CONSENT','CONFIRMED','INVALIDATED','REJECTED')",
            name="ck_proposals_proposal_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    room_id: Mapped[str] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    round: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)
<<<<<<< HEAD
=======
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
    solver_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    proposal_status: Mapped[str] = mapped_column(String(40), default="PROPOSED")
    created_by_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    finalized_by_member_id: Mapped[str | None] = mapped_column(
        ForeignKey("room_members.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProposalConditionInput(Base):
    __tablename__ = "proposal_condition_inputs"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            "room_member_id",
            name="uq_proposal_condition_inputs_proposal_member",
        ),
    )

    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), primary_key=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), primary_key=True
    )
    condition_submission_id: Mapped[str] = mapped_column(
        ForeignKey("condition_submissions.id", ondelete="RESTRICT")
    )


class ProposalAssignment(Base):
    __tablename__ = "proposal_assignments"
    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at", name="ck_proposal_assignments_time_range"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), index=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), index=True
    )
    room_role_id: Mapped[str] = mapped_column(
        ForeignKey("room_roles.id", ondelete="RESTRICT"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ProposalConsent(Base):
    __tablename__ = "proposal_consents"
    __table_args__ = (
        CheckConstraint(
<<<<<<< HEAD
            "status IN ('PENDING', 'AGREED', 'WITHDRAWN', 'REJECTED')",
=======
            "status IN ("
            "'PENDING','AGREED','WITHDRAWN','REJECTED',"
            "'pending','agreed','review')",
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
            name="ck_proposal_consents_status",
        ),
    )

    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), primary_key=True
    )
    room_member_id: Mapped[str] = mapped_column(
        ForeignKey("room_members.id", ondelete="CASCADE"), primary_key=True
    )
<<<<<<< HEAD
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
=======
    # API uses lowercase agreed/pending/review; uppercase kept for v2.1 semantics
    status: Mapped[str] = mapped_column(String(20), default="pending")
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
