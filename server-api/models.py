"""Application ORM entrypoint — re-exports db_v21 with legacy field aliases.

Workflow/admin code may use historical names (Member, config, host_id, …).
Physical schema lives in db_v21 / Alembic v21.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import synonym

SEOUL = ZoneInfo("Asia/Seoul")

from db_v21 import (  # noqa: F401 — register metadata
    Account,
    AccountSession,
    AdminAuditLog,
    AdminOtp,
    AdminRateLimit,
    AiDraft,
    Announcement,
    Base,
    ConditionAvailableSlot,
    ConditionRolePreference,
    ConditionSubmission,
    IdempotencyRecord,
    PasswordResetToken,
    Proposal,
    ProposalAssignment,
    ProposalConditionInput,
    ProposalConsent,
    Room,
    RoomControl,
    RoomEvent,
    RoomMember,
    RoomRole,
    ServiceControl,
    now,
    uid,
)

# --- Room legacy aliases -------------------------------------------------------
Room.status = synonym("progress_status")
Room.round = synonym("current_round")
Room.config = synonym("meeting_settings")
Room.host_id = synonym("host_member_id")

# --- Member / condition / AI / consent aliases ---------------------------------
RoomMember.created_at = synonym("joined_at")
AiDraft.member_id = synonym("room_member_id")
ConditionSubmission.member_id = synonym("room_member_id")
ConditionSubmission.created_at = synonym("submitted_at")
ProposalConsent.member_id = synonym("room_member_id")

# Public names used by workflow.py / database.py
Member = RoomMember
Submission = ConditionSubmission
AIDraft = AiDraft
ConsentRow = ProposalConsent

# Stub kept for imports that still mention SchemaVersion (no-op table in v2.1)
class SchemaVersion:  # pragma: no cover — unused after Alembic ownership
    pass


def room_time_bounds(settings: dict) -> tuple[datetime, datetime]:
    """Derive rooms.starts_at / ends_at from meeting dates in Asia/Seoul (+1 day end)."""
    dates = sorted(settings.get("dates") or [])
    if not dates:
        start = now()
        return start, start + timedelta(days=1)
    start = datetime.fromisoformat(dates[0]).replace(tzinfo=SEOUL)
    end = datetime.fromisoformat(dates[-1]).replace(tzinfo=SEOUL) + timedelta(days=1)
    if end <= start:
        end = start + timedelta(days=1)
    return start, end


def sync_room_roles(db, room: Room, roles: list[str], role_needs: dict | None = None) -> None:
    """Replace room_roles from CreateMeeting roles / roleNeeds."""
    from sqlalchemy import delete

    db.execute(delete(RoomRole).where(RoomRole.room_id == room.id))
    needs = role_needs or {}
    for name in roles or []:
        db.add(
            RoomRole(
                room_id=room.id,
                name=name,
                required_count=int(needs.get(name, 1) or 1),
            )
        )


def ensure_guest_account(db, nickname: str = "") -> Account:
    """Disposable GUEST account for anonymous create/join (not email USER signup)."""
    from argon2 import PasswordHasher

    account = Account(
        login_email=f"guest-{uid()}@local.invalid",
        password_hash=PasswordHasher().hash(uid()),
        account_type="GUEST",
        account_status="ACTIVE",
        approved=True,
    )
    db.add(account)
    db.flush()
    return account


def resolve_user_account(db, account_token: str | None) -> Account | None:
    """Resolve an email USER session token; rejects GUEST/ADMIN and expired/revoked."""
    if not account_token:
        return None
    import hashlib
    from sqlalchemy import select

    token = account_token.removeprefix("Bearer ").strip() if account_token.startswith("Bearer ") else account_token.strip()
    if not token:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.scalar(select(AccountSession).where(AccountSession.token_hash == digest))
    if not row or row.revoked_at is not None:
        return None
    expires = row.expires_at
    if expires is None:
        return None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now():
        return None
    account = db.get(Account, row.account_id)
    if (
        not account
        or account.account_type != "USER"
        or account.account_status != "ACTIVE"
        or not account.approved
    ):
        return None
    return account


__all__ = [
    "AIDraft",
    "Account",
    "AccountSession",
    "AdminAuditLog",
    "AdminOtp",
    "AdminRateLimit",
    "Announcement",
    "Base",
    "ConditionAvailableSlot",
    "ConditionRolePreference",
    "ConditionSubmission",
    "ConsentRow",
    "IdempotencyRecord",
    "Member",
    "PasswordResetToken",
    "Proposal",
    "ProposalAssignment",
    "ProposalConditionInput",
    "ProposalConsent",
    "Room",
    "RoomControl",
    "RoomEvent",
    "RoomMember",
    "RoomRole",
    "SchemaVersion",
    "ServiceControl",
    "Submission",
    "ensure_guest_account",
    "now",
    "resolve_user_account",
    "room_time_bounds",
    "sync_room_roles",
    "uid",
]
