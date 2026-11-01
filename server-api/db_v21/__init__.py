"""Schema v2.1 ORM package (parallel to legacy ok_*). Single Base for Alembic v21."""
from db_v21.base import Base, now, uid
from db_v21.models import (  # noqa: F401 — register metadata
    Account,
    AccountSession,
    AdminAuditLog,
    AdminOtp,
    AdminRateLimit,
    AiDraft,
    Announcement,
    ConditionAvailableSlot,
    ConditionRolePreference,
    ConditionSubmission,
<<<<<<< HEAD
=======
    IdempotencyRecord,
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
    PasswordResetToken,
    Proposal,
    ProposalAssignment,
    ProposalConditionInput,
    ProposalConsent,
    Room,
    RoomControl,
<<<<<<< HEAD
    RoomCycleArchive,
=======
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
    RoomEvent,
    RoomMember,
    RoomRole,
    ServiceControl,
)

__all__ = [
    "Base",
    "uid",
    "now",
    "Account",
    "AccountSession",
    "PasswordResetToken",
    "Room",
    "RoomMember",
    "RoomRole",
    "AiDraft",
    "ConditionSubmission",
    "ConditionAvailableSlot",
    "ConditionRolePreference",
    "Proposal",
    "ProposalConditionInput",
    "ProposalAssignment",
    "ProposalConsent",
    "ServiceControl",
    "RoomControl",
    "AdminAuditLog",
    "Announcement",
    "RoomEvent",
    "AdminOtp",
    "AdminRateLimit",
<<<<<<< HEAD
    "RoomCycleArchive",
=======
    "IdempotencyRecord",
>>>>>>> 4a28f5df6e17f8be24ab6bebfa6f3bc599e6b284
]
