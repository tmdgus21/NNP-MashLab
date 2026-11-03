"""Authorize and persist queued Agent runs with request idempotency."""
from __future__ import annotations

import hashlib
import json
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Annotated
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    ValidationError,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from db_v21.base import now
from db_v21.models.account import Account
from db_v21.models.admin import IdempotencyRecord
from db_v21.models.agent import AgentRun
from db_v21.models.room import Room, RoomMember
from services.meeting_domain import agent_final_exists
from potato_agent.models import MeetingSnapshot
from services.meeting_snapshot import (
    SnapshotBuildError,
    build_meeting_snapshot,
)


class AgentRunServiceError(Exception):
    """Base error with an API-ready status and stable error code."""

    status_code = 500
    code = "AGENT_RUN_ERROR"


class InvalidAgentRunRequestError(AgentRunServiceError):
    status_code = 422
    code = "INVALID_AGENT_RUN_REQUEST"


class UnsupportedUserRequestError(AgentRunServiceError):
    status_code = 422
    code = "USER_REQUEST_NOT_SUPPORTED"


class AuthenticationRequiredError(AgentRunServiceError):
    status_code = 401
    code = "AUTHENTICATION_REQUIRED"


class AccountNotAllowedError(AgentRunServiceError):
    status_code = 403
    code = "ACCOUNT_NOT_ALLOWED"


class RoomMembershipRequiredError(AgentRunServiceError):
    status_code = 403
    code = "ROOM_MEMBERSHIP_REQUIRED"


class RoomHostRequiredError(AgentRunServiceError):
    status_code = 403
    code = "ROOM_HOST_REQUIRED"


class MeetingNotFoundError(AgentRunServiceError):
    status_code = 404
    code = "MEETING_NOT_FOUND"


class InputRevisionConflictError(AgentRunServiceError):
    status_code = 409
    code = "INPUT_REVISION_CONFLICT"

    def __init__(self, expected: int, current: int):
        super().__init__(
            f"expected input revision {expected}, current revision is {current}"
        )
        self.expected_revision = expected
        self.current_revision = current


class RoundAlreadyFinalizedError(AgentRunServiceError):
    """The current coordination round already has a final result; a new Run would be wasted."""

    status_code = 409
    code = "ROUND_ALREADY_FINALIZED"


class IdempotencyConflictError(AgentRunServiceError):
    status_code = 409
    code = "IDEMPOTENCY_KEY_REUSED"


class CorruptIdempotencyRecordError(AgentRunServiceError):
    status_code = 409
    code = "IDEMPOTENCY_RECORD_INCOMPLETE"


class UnsupportedDatabaseDialectError(AgentRunServiceError):
    status_code = 500
    code = "UNSUPPORTED_DATABASE_DIALECT"


class AgentRunPersistenceError(AgentRunServiceError):
    status_code = 500
    code = "AGENT_RUN_PERSISTENCE_ERROR"


class StartAgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_input_revision: Annotated[StrictInt, Field(ge=1)] = Field(
        alias="expectedInputRevision"
    )
    user_request: StrictStr | None = Field(default=None, alias="userRequest")


@dataclass(frozen=True)
class RoomActor:
    account_id: str
    room_member_id: str
    is_host: bool


@dataclass(frozen=True)
class AgentRunResult:
    run_id: str
    agent_session_id: str
    meeting_id: str
    status: str
    source_revision: int
    input_snapshot_hash: str
    created_by_account_id: str
    created_by_member_id: str
    snapshot: MeetingSnapshot
    replayed: bool


def _request_model(request: StartAgentRunRequest | dict) -> StartAgentRunRequest:
    try:
        return (
            request
            if isinstance(request, StartAgentRunRequest)
            else StartAgentRunRequest.model_validate(request)
        )
    except ValidationError as exc:
        raise InvalidAgentRunRequestError(
            "request must contain a positive expectedInputRevision and only "
            "the supported null userRequest"
        ) from exc


def _authorize_room_actor(
    db: Session,
    room: Room,
    actor_account_id: str | None,
) -> RoomActor:
    if not actor_account_id:
        raise AuthenticationRequiredError("authenticated account is required")
    account = db.scalar(
        select(Account).where(
            Account.id == actor_account_id,
            Account.account_type == "USER",
            Account.account_status == "ACTIVE",
            Account.approved.is_(True),
        )
    )
    if account is None:
        raise AccountNotAllowedError("account is not an active authenticated user")
    member = db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id,
            RoomMember.account_id == account.id,
            RoomMember.membership_status == "ACTIVE",
        )
    )
    if member is None:
        raise RoomMembershipRequiredError(
            "an active room membership is required to start an Agent run"
        )
    return RoomActor(
        account_id=account.id,
        room_member_id=member.id,
        is_host=member.id == room.host_member_id and member.room_role == "OWNER",
    )


def authorize_room_host(db: Session, *, room_id: str, actor_account_id: str) -> RoomActor:
    """Apply the shared host-only authorization rule for host-specific operations."""
    room = db.scalar(
        select(Room).where(Room.id == room_id, Room.deleted_at.is_(None))
    )
    if room is None:
        raise MeetingNotFoundError("meeting does not exist")
    actor = _authorize_room_actor(db, room, actor_account_id)
    if not actor.is_host:
        raise RoomHostRequiredError("only the room host may perform this operation")
    return actor


def authorize_room_member(
    db: Session, *, room_id: str, actor_account_id: str
) -> RoomActor:
    """Require an active authenticated user and active membership in a room."""
    room = db.scalar(
        select(Room).where(Room.id == room_id, Room.deleted_at.is_(None))
    )
    if room is None:
        raise MeetingNotFoundError("meeting does not exist")
    return _authorize_room_actor(db, room, actor_account_id)


def _scope(room_id: str, account_id: str) -> str:
    owner_hash = hashlib.sha256(
        f"{room_id}:{account_id}".encode("utf-8")
    ).hexdigest()
    return f"agent-run:{owner_hash[:54]}"


def _digest_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _request_hash(
    *, room_id: str, account_id: str, request: StartAgentRunRequest
) -> str:
    payload = {
        "meetingId": room_id,
        "actorAccountId": account_id,
        "expectedInputRevision": request.expected_input_revision,
        "userRequest": request.user_request,
    }
    return _digest_key(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


def _claim_idempotency_record(
    db: Session,
    *,
    scope: str,
    key_hash: str,
    request_hash: str,
) -> tuple[IdempotencyRecord, bool]:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = postgresql_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise UnsupportedDatabaseDialectError(
            f"Agent run idempotency is unsupported for {dialect!r}"
        )

    candidate_id = str(uuid4())
    statement = (
        insert(IdempotencyRecord)
        .values(
            id=candidate_id,
            scope=scope,
            key_hash=key_hash,
            request_hash=request_hash,
            resource_type="agent_run",
            resource_id=None,
            payload=None,
            created_at=now(),
        )
        .on_conflict_do_nothing(
            index_elements=[
                IdempotencyRecord.scope,
                IdempotencyRecord.key_hash,
            ]
        )
        .returning(IdempotencyRecord.id)
    )
    inserted_id = db.execute(statement).scalar_one_or_none()
    record = db.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key_hash == key_hash,
        )
        .with_for_update()
    )
    if record is None:
        raise AgentRunPersistenceError(
            "idempotency reservation could not be read after insert"
        )
    return record, inserted_id == candidate_id


def _transaction_context(db: Session) -> AbstractContextManager:
    if not db.in_transaction():
        return db.begin()
    if db.get_bind().dialect.name == "sqlite":
        connection = db.connection()
        driver_connection = connection.connection.driver_connection
        if not driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
    return db.begin_nested()


def _load_replayed_run(
    db: Session,
    *,
    record: IdempotencyRecord,
    request_hash: str,
    actor: RoomActor,
    room_id: str,
) -> AgentRunResult:
    if record.request_hash != request_hash:
        raise IdempotencyConflictError(
            "idempotency key was already used for a different request"
        )
    if record.resource_type != "agent_run" or not record.resource_id:
        raise CorruptIdempotencyRecordError(
            "idempotency record does not reference a completed Agent run"
        )
    run = db.get(AgentRun, record.resource_id)
    if run is None or run.room_id != room_id:
        raise CorruptIdempotencyRecordError(
            "idempotency record references a missing or unrelated Agent run"
        )
    if run.created_by_member_id != actor.room_member_id:
        raise CorruptIdempotencyRecordError(
            "idempotency record owner does not match the run creator"
        )
    try:
        snapshot = MeetingSnapshot.model_validate(run.input_snapshot)
    except ValidationError as exc:
        raise AgentRunPersistenceError(
            "persisted Agent run snapshot is invalid"
        ) from exc
    if (
        snapshot.run_id != run.id
        or snapshot.agent_session_id != run.agent_session_id
        or snapshot.meeting_id != run.room_id
        or snapshot.input_revision != run.source_revision
        or snapshot.input_snapshot_hash != run.input_snapshot_hash
    ):
        raise AgentRunPersistenceError(
            "persisted Agent run metadata does not match its immutable snapshot"
        )
    return AgentRunResult(
        run_id=run.id,
        agent_session_id=run.agent_session_id,
        meeting_id=run.room_id,
        status=run.status,
        source_revision=run.source_revision,
        input_snapshot_hash=run.input_snapshot_hash,
        created_by_account_id=actor.account_id,
        created_by_member_id=actor.room_member_id,
        snapshot=snapshot,
        replayed=True,
    )


def start_agent_run(
    db: Session,
    *,
    room_id: str,
    actor_account_id: str | None,
    idempotency_key: str,
    request: StartAgentRunRequest | dict,
) -> AgentRunResult:
    """Persist a queued run and its idempotency row in one transaction.

    `actor_account_id` must come from the already-authenticated API principal.
    Start-run authorization requires active membership, not host status, per the
    Agent contract. Host-only operations use `authorize_room_host`.
    If the caller already has an active request transaction, the writes are
    contained in a savepoint and remain part of that transaction; otherwise this
    service owns commit/rollback. The returned snapshot is fully detached.
    """
    parsed_request = _request_model(request)
    if parsed_request.user_request is not None:
        raise UnsupportedUserRequestError(
            "non-null userRequest is not persisted by the current AgentRun model"
        )
    if (
        not isinstance(idempotency_key, str)
        or not idempotency_key.strip()
        or len(idempotency_key) > 200
    ):
        raise InvalidAgentRunRequestError(
            "Idempotency-Key must contain 1 to 200 non-whitespace characters"
        )
    if not room_id or not isinstance(room_id, str):
        raise InvalidAgentRunRequestError("meeting identifier is required")

    try:
        with _transaction_context(db):
            room = db.scalar(
                select(Room)
                .where(Room.id == room_id, Room.deleted_at.is_(None))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if room is None:
                raise MeetingNotFoundError("meeting does not exist")
            actor = _authorize_room_actor(db, room, actor_account_id)
            scope = _scope(room.id, actor.account_id)
            request_hash = _request_hash(
                room_id=room.id,
                account_id=actor.account_id,
                request=parsed_request,
            )
            record, created = _claim_idempotency_record(
                db,
                scope=scope,
                key_hash=_digest_key(idempotency_key),
                request_hash=request_hash,
            )
            if not created:
                return _load_replayed_run(
                    db,
                    record=record,
                    request_hash=request_hash,
                    actor=actor,
                    room_id=room.id,
                )

            # After the replay check, so an already-created Run is still returned.
            if agent_final_exists(db, room):
                raise RoundAlreadyFinalizedError(
                    "the current coordination round already has a final result"
                )

            expected_revision = parsed_request.expected_input_revision
            if room.agent_input_revision != expected_revision:
                raise InputRevisionConflictError(
                    expected=expected_revision,
                    current=room.agent_input_revision,
                )

            run_id = str(uuid4())
            session_id = str(uuid4())
            snapshot = build_meeting_snapshot(
                db,
                room_id=room.id,
                agent_session_id=session_id,
                run_id=run_id,
                consent_round=1,
            )
            if snapshot.input_revision != expected_revision:
                raise InputRevisionConflictError(
                    expected=expected_revision,
                    current=snapshot.input_revision,
                )

            current_room = db.scalar(
                select(Room)
                .where(Room.id == room.id, Room.deleted_at.is_(None))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                current_room is None
                or current_room.agent_input_revision != snapshot.input_revision
            ):
                current_revision = (
                    current_room.agent_input_revision
                    if current_room is not None
                    else 0
                )
                raise InputRevisionConflictError(
                    expected=snapshot.input_revision,
                    current=current_revision,
                )

            run = AgentRun(
                id=run_id,
                agent_session_id=session_id,
                room_id=room.id,
                created_by_member_id=actor.room_member_id,
                source_revision=snapshot.input_revision,
                input_snapshot_hash=snapshot.input_snapshot_hash,
                input_snapshot=snapshot.model_dump(mode="json"),
                consent_round=snapshot.consent_round,
                status="QUEUED",
                approval_status="NOT_REQUESTED",
                attempt_number=1,
            )
            db.add(run)
            db.flush()

            record.resource_type = "agent_run"
            record.resource_id = run.id
            record.payload = {
                "agentSessionId": session_id,
                "runId": run.id,
                "inputRevision": snapshot.input_revision,
                "inputSnapshotHash": snapshot.input_snapshot_hash,
                "status": "QUEUED",
            }
            db.flush()

            return AgentRunResult(
                run_id=run.id,
                agent_session_id=session_id,
                meeting_id=room.id,
                status="QUEUED",
                source_revision=run.source_revision,
                input_snapshot_hash=run.input_snapshot_hash,
                created_by_account_id=actor.account_id,
                created_by_member_id=actor.room_member_id,
                snapshot=snapshot,
                replayed=False,
            )
    except SnapshotBuildError:
        raise
