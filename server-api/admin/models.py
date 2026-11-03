"""Admin ORM aliases over db_v21 (single Base with workflow tables)."""
from datetime import datetime

from sqlalchemy.orm import synonym

from db_v21 import (
    Account,
    AccountSession,
    AdminAuditLog,
    AdminOtp,
    AdminRateLimit,
    IdempotencyRecord,
)
from db_v21.base import now, uid

# --- Account: email / role / frozen aliases ------------------------------------
Account.email = synonym("login_email")
Account.role = synonym("admin_role")


@property
def _account_frozen(self) -> bool:
    return self.account_status == "FROZEN"


@_account_frozen.setter
def _account_frozen(self, value: bool) -> None:
    if value:
        self.account_status = "FROZEN"
    elif self.account_status == "FROZEN":
        self.account_status = "ACTIVE"


Account.frozen = _account_frozen

# --- Session: digest PK → token_hash; revoked → revoked_at; expires ------------
AccountSession.digest = synonym("token_hash")
AccountSession.expires = synonym("expires_at")


@property
def _session_revoked(self) -> bool:
    return self.revoked_at is not None


@_session_revoked.setter
def _session_revoked(self, value: bool) -> None:
    if value and self.revoked_at is None:
        self.revoked_at = now()
    elif not value:
        self.revoked_at = None


AccountSession.revoked = _session_revoked

# --- Audit field aliases -------------------------------------------------------
AdminAuditLog.actor = synonym("admin_account_id")
AdminAuditLog.action = synonym("action_type")
AdminAuditLog.target = synonym("target_id")
AdminAuditLog.created_at = synonym("occurred_at")


@property
def _audit_data(self) -> dict:
    return {}


@_audit_data.setter
def _audit_data(self, value: dict) -> None:
    if value and not self.reason:
        self.reason = str(value)[:1000]


AdminAuditLog.data = _audit_data

OTP = AdminOtp
AdminSession = AccountSession
Audit = AdminAuditLog
RateBucket = AdminRateLimit
CycleArchive = IdempotencyRecord


def _iso(value):
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def _iso_out(value):
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


class Lifecycle:
    """View over room.meeting_settings['_lifecycle'] + RoomControl.

    Attribute reads always reflect the current room JSON so expire()/ensure()
    callers that keep an earlier reference still see updates.
    """

    __slots__ = ("_room", "_control")

    def __init__(self, room, control):
        self._room = room
        self._control = control

    @property
    def room_id(self):
        return self._room.id

    def _data(self) -> dict:
        return dict((self._room.meeting_settings or {}).get("_lifecycle") or {})

    def _set(self, **fields) -> None:
        settings = dict(self._room.meeting_settings or {})
        data = dict(settings.get("_lifecycle") or {})
        data.update(fields)
        settings["_lifecycle"] = data
        self._room.meeting_settings = settings

    @property
    def cycle(self):
        return int(self._data().get("cycle", 1))

    @cycle.setter
    def cycle(self, value):
        self._set(cycle=int(value))

    @property
    def state(self):
        return self._data().get("state", "ACTIVE")

    @state.setter
    def state(self, value):
        self._set(state=value)

    @property
    def management(self):
        return "ENABLED" if self._control.control_status == "ACTIVE" else "DISABLED"

    @management.setter
    def management(self, value):
        self._control.control_status = "ACTIVE" if value == "ENABLED" else "SUSPENDED"

    @property
    def scheduled_date(self):
        return self._data().get("scheduled_date") or max(
            (self._room.meeting_settings or {}).get("dates") or ["1970-01-01"]
        )

    @scheduled_date.setter
    def scheduled_date(self, value):
        self._set(scheduled_date=value)

    @property
    def closes_at(self):
        return _iso(self._data().get("closes_at"))

    @closes_at.setter
    def closes_at(self, value):
        self._set(closes_at=_iso_out(value))

    @property
    def actual_end(self):
        return _iso(self._data().get("actual_end"))

    @actual_end.setter
    def actual_end(self, value):
        self._set(actual_end=_iso_out(value))

    @property
    def starts_at(self):
        return _iso(self._data().get("starts_at"))

    @starts_at.setter
    def starts_at(self, value):
        self._set(starts_at=_iso_out(value))

    @property
    def base_round(self):
        return int(self._data().get("base_round", -1))

    @base_round.setter
    def base_round(self, value):
        self._set(base_round=int(value))

    def persist(self) -> None:
        # Property setters already write through; ensure control status synced.
        self.management = self.management


__all__ = [
    "Account",
    "AdminSession",
    "Audit",
    "CycleArchive",
    "Lifecycle",
    "OTP",
    "RateBucket",
    "now",
    "uid",
]
