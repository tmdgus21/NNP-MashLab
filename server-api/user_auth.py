"""Email USER signup/login with OTP — separate from admin OTP and GUEST placeholders."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from database import session
from mail_otp import send_otp_email
from models import (
    AIDraft,
    Account,
    AccountSession,
    PasswordResetToken,
    Room,
    RoomEvent,
    RoomMember,
    Submission,
    UserAuthChallenge,
    now,
)
from db_v21.models.schedule import (
    ScheduleResponse,
    ScheduleResponseRange,
    ScheduleRun,
    ScheduleVote,
    ScheduleVoteBallot,
)
from nickname_generator import generate_nickname

OTP_TTL = timedelta(minutes=5)
RESEND_AFTER = timedelta(seconds=60)
MAX_ATTEMPTS = 5
MAX_SENDS_PER_HOUR = 10
ANONYMIZED_MEMBER_NICKNAME = "탈퇴한 사용자"


def _utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


router = APIRouter(prefix="/v1/auth", tags=["User authentication"])
PASSWORDS = PasswordHasher()
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
GUEST_DOMAIN = "@local.invalid"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Register(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=1024)


class Login(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class ChallengeBody(Input):
    challenge: str = Field(min_length=32, max_length=64)


class VerifyBody(Input):
    challenge: str = Field(min_length=32, max_length=64)
    code: str = Field(pattern=r"^\d{6}$")


class NicknamePatch(Input):
    nickname: str = Field(min_length=1, max_length=30)


class DeleteAccount(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    password: str = Field(min_length=1, max_length=1024)


def db_session():
    # Commit on HTTPException so OTP attempt counters survive 4xx responses.
    with session() as db:
        try:
            yield db
            db.commit()
        except HTTPException:
            db.commit()
            raise
        except Exception:
            db.rollback()
            raise


def fail(status: int, message: str):
    raise HTTPException(status, detail=message)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def otp_secret() -> str:
    secret = os.getenv("APP_SESSION_SECRET") or os.getenv("USER_OTP_SECRET")
    if not secret and os.getenv("DATABASE_URL", "").startswith("sqlite"):
        secret = "isolated-test-secret-not-for-production"
    if not secret or len(secret) < 16:
        fail(503, "세션 설정이 준비되지 않았습니다.")
    return secret


def otp_mac(challenge: str, code: str) -> str:
    return hmac.new(
        otp_secret().encode(),
        f"{challenge}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def normalize_email(value: str) -> str:
    return value.strip().lower()


def validate_email(email: str) -> str:
    email = normalize_email(email)
    if not EMAIL_RE.fullmatch(email) or email.endswith(GUEST_DOMAIN):
        fail(422, "유효한 이메일을 입력해 주세요.")
    return email


def issue_session(db, account: Account) -> tuple[str, AccountSession]:
    token = secrets.token_urlsafe(48)
    row = AccountSession(
        account_id=account.id,
        token_hash=digest(token),
        csrf=None,
        expires_at=now() + timedelta(days=30),
    )
    db.add(row)
    account.last_login_at = now()
    return token, row


def account_from_authorization(db, authorization: str | None) -> Account:
    if not authorization or not authorization.startswith("Bearer "):
        fail(401, "로그인이 필요합니다.")
    token = authorization[7:].strip()
    row = db.scalar(select(AccountSession).where(AccountSession.token_hash == digest(token)))
    if not row or row.revoked_at is not None or _utc(row.expires_at) <= now():
        fail(401, "로그인이 필요합니다.")
    account = db.get(Account, row.account_id)
    if not account or account.account_type != "USER" or account.account_status != "ACTIVE" or not account.approved:
        fail(403, "사용할 수 없는 계정입니다.")
    return account


def _challenge_response(row: UserAuthChallenge) -> dict:
    return {
        "challenge": row.challenge,
        "expiresIn": 300,
        "resendAfter": 60,
        "purpose": row.purpose,
    }


def _rate_limit_sends(db, email: str, purpose: str) -> None:
    cutoff = now() - timedelta(hours=1)
    recent = list(
        db.scalars(
            select(UserAuthChallenge).where(
                UserAuthChallenge.email == email,
                UserAuthChallenge.purpose == purpose,
                UserAuthChallenge.sent_at >= cutoff,
            )
        )
    )
    if len(recent) >= MAX_SENDS_PER_HOUR:
        fail(429, "인증번호 요청이 너무 많습니다. 잠시 후 다시 시도하세요.")


def _invalidate_open_challenges(db, email: str, purpose: str) -> None:
    for row in db.scalars(
        select(UserAuthChallenge).where(
            UserAuthChallenge.email == email,
            UserAuthChallenge.purpose == purpose,
            UserAuthChallenge.used_at.is_(None),
        )
    ):
        row.used_at = now()


def _deliver_user_otp(email: str, code: str) -> None:
    send_otp_email(
        email,
        code,
        subject="[Potato Meet] 이메일 인증번호",
        body=(
            f"인증번호: {code}\n"
            "5분 안에 입력해 주세요. 요청하지 않았다면 이 메일을 무시하세요."
        ),
    )


def _issue_challenge(
    db,
    *,
    email: str,
    purpose: str,
    account: Account | None,
    password_hash: str | None,
) -> UserAuthChallenge:
    _rate_limit_sends(db, email, purpose)
    latest = db.scalar(
        select(UserAuthChallenge)
        .where(
            UserAuthChallenge.email == email,
            UserAuthChallenge.purpose == purpose,
            UserAuthChallenge.used_at.is_(None),
        )
        .order_by(UserAuthChallenge.sent_at.desc())
    )
    if latest and _utc(latest.sent_at) + RESEND_AFTER > now() and latest.used_at is None:
        if _utc(latest.expires_at) > now():
            fail(429, "인증번호 재발송은 60초 후 가능합니다.")

    challenge = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        _deliver_user_otp(email, code)
    except Exception:
        fail(503, "인증 메일을 보내지 못했습니다. 잠시 후 다시 시도하세요.")

    _invalidate_open_challenges(db, email, purpose)
    row = UserAuthChallenge(
        account_id=account.id if account else None,
        email=email,
        purpose=purpose,
        challenge=challenge,
        code_digest=otp_mac(challenge, code),
        password_hash=password_hash,
        expires_at=now() + OTP_TTL,
        sent_at=now(),
        used_at=None,
        attempt_count=0,
        max_attempts=MAX_ATTEMPTS,
    )
    db.add(row)
    db.flush()
    return row


def _load_challenge(db, challenge: str, purpose: str) -> UserAuthChallenge:
    row = db.scalar(
        select(UserAuthChallenge)
        .where(UserAuthChallenge.challenge == challenge)
        .with_for_update()
    )
    if not row or row.purpose != purpose:
        fail(401, "인증 요청이 올바르지 않습니다.")
    return row


def _assert_challenge_open(row: UserAuthChallenge) -> None:
    if row.used_at is not None:
        fail(401, "이미 사용된 인증 요청입니다. 다시 시도해 주세요.")
    if _utc(row.expires_at) <= now():
        fail(401, "인증번호가 만료됐습니다. 다시 요청해 주세요.")
    if row.attempt_count >= row.max_attempts:
        fail(429, "인증 시도 횟수를 초과했습니다. 다시 로그인해 주세요.")


def _assert_challenge_resendable(row: UserAuthChallenge) -> None:
    """Resend allowed after expiry; blocked only when already used."""
    if row.used_at is not None:
        fail(401, "이미 사용된 인증 요청입니다. 다시 시도해 주세요.")


@router.post("/register", status_code=201)
def register(body: Register, db=Depends(db_session)):
    email = validate_email(body.email)
    if len(body.password) < 12:
        fail(422, "비밀번호는 12자 이상이어야 합니다.")
    existing = db.scalar(
        select(Account).where(Account.login_email == email, Account.account_type == "USER")
    )
    if existing and existing.account_status == "ACTIVE" and existing.approved:
        fail(409, "이미 등록된 이메일입니다.")
    row = _issue_challenge(
        db,
        email=email,
        purpose="REGISTER",
        account=None,
        password_hash=PASSWORDS.hash(body.password),
    )
    return _challenge_response(row)


@router.post("/register/resend")
def register_resend(body: ChallengeBody, db=Depends(db_session)):
    previous = _load_challenge(db, body.challenge, "REGISTER")
    _assert_challenge_resendable(previous)
    if not previous.password_hash:
        fail(401, "인증 요청이 올바르지 않습니다.")
    row = _issue_challenge(
        db,
        email=previous.email,
        purpose="REGISTER",
        account=None,
        password_hash=previous.password_hash,
    )
    return _challenge_response(row)


@router.post("/register/verify")
def register_verify(body: VerifyBody, db=Depends(db_session)):
    row = _load_challenge(db, body.challenge, "REGISTER")
    _assert_challenge_open(row)
    if not secrets.compare_digest(row.code_digest, otp_mac(body.challenge, body.code)):
        row.attempt_count += 1
        fail(401, "인증번호가 올바르지 않거나 만료됐습니다.")
    if not row.password_hash:
        fail(401, "인증 요청이 올바르지 않습니다.")
    existing = db.scalar(
        select(Account).where(Account.login_email == row.email, Account.account_type == "USER")
    )
    if existing and existing.account_status == "ACTIVE" and existing.approved:
        fail(409, "이미 등록된 이메일입니다.")
    nickname = generate_nickname()
    account = Account(
        login_email=row.email,
        password_hash=row.password_hash,
        nickname=nickname,
        account_type="USER",
        account_status="ACTIVE",
        approved=True,
    )
    db.add(account)
    db.flush()
    row.used_at = now()
    row.account_id = account.id
    token, _ = issue_session(db, account)
    return {
        "accountId": account.id,
        "email": account.login_email,
        "nickname": account.nickname,
        "token": token,
    }


@router.post("/login")
def login(body: Login, db=Depends(db_session)):
    email = validate_email(body.email)
    account = db.scalar(
        select(Account).where(Account.login_email == email, Account.account_type == "USER").with_for_update()
    )
    valid = False
    if account:
        try:
            valid = PASSWORDS.verify(account.password_hash, body.password)
        except (VerificationError, InvalidHashError):
            valid = False
    else:
        PASSWORDS.hash(body.password)
    if not account or not valid:
        fail(401, "이메일 또는 비밀번호를 확인하세요.")
    if account.account_status != "ACTIVE" or not account.approved:
        fail(403, "사용할 수 없는 계정입니다.")
    row = _issue_challenge(
        db,
        email=email,
        purpose="LOGIN",
        account=account,
        password_hash=None,
    )
    return _challenge_response(row)


@router.post("/login/resend")
def login_resend(body: ChallengeBody, db=Depends(db_session)):
    previous = _load_challenge(db, body.challenge, "LOGIN")
    _assert_challenge_resendable(previous)
    account = db.get(Account, previous.account_id) if previous.account_id else None
    if not account or account.account_type != "USER":
        fail(401, "인증 요청이 올바르지 않습니다.")
    row = _issue_challenge(
        db,
        email=previous.email,
        purpose="LOGIN",
        account=account,
        password_hash=None,
    )
    return _challenge_response(row)


@router.post("/login/verify")
def login_verify(body: VerifyBody, db=Depends(db_session)):
    row = _load_challenge(db, body.challenge, "LOGIN")
    _assert_challenge_open(row)
    if not secrets.compare_digest(row.code_digest, otp_mac(body.challenge, body.code)):
        row.attempt_count += 1
        fail(401, "인증번호가 올바르지 않거나 만료됐습니다.")
    account = db.get(Account, row.account_id) if row.account_id else None
    if not account or account.account_type != "USER":
        fail(401, "인증 요청이 올바르지 않습니다.")
    if account.account_status != "ACTIVE" or not account.approved:
        fail(403, "사용할 수 없는 계정입니다.")
    row.used_at = now()
    token, _ = issue_session(db, account)
    return {
        "accountId": account.id,
        "email": account.login_email,
        "nickname": account.nickname,
        "token": token,
    }


@router.get("/me")
def me(authorization: str | None = Header(default=None), db=Depends(db_session)):
    account = account_from_authorization(db, authorization)
    return {
        "accountId": account.id,
        "email": account.login_email,
        "nickname": account.nickname,
        "accountType": account.account_type,
    }


@router.patch("/me/nickname")
def patch_nickname(
    body: NicknamePatch,
    authorization: str | None = Header(default=None),
    db=Depends(db_session),
):
    account = account_from_authorization(db, authorization)
    nick = body.nickname.strip()
    if not nick:
        fail(422, "닉네임을 입력해 주세요.")
    if len(nick) > 30:
        fail(422, "닉네임은 30자 이하여야 합니다.")
    account.nickname = nick
    return {
        "accountId": account.id,
        "email": account.login_email,
        "nickname": account.nickname,
        "accountType": account.account_type,
    }


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db=Depends(db_session)):
    if not authorization or not authorization.startswith("Bearer "):
        fail(401, "로그인이 필요합니다.")
    token = authorization[7:].strip()
    row = db.scalar(select(AccountSession).where(AccountSession.token_hash == digest(token)).with_for_update())
    if not row or row.revoked_at is not None:
        fail(401, "로그인이 필요합니다.")
    account = db.get(Account, row.account_id)
    if not account or account.account_type != "USER":
        fail(403, "사용할 수 없는 계정입니다.")
    row.revoked_at = now()
    return {"ok": True}


def _scrub_text(value: str | None, tokens: list[str]) -> str | None:
    if not value:
        return value
    out = value
    for token in tokens:
        if token and token in out:
            out = out.replace(token, ANONYMIZED_MEMBER_NICKNAME)
    return out


def _delete_account_side_effects(db, account: Account) -> None:
    """Anonymize memberships, purge leaver PII, transfer ownership; then caller deletes account."""
    account_id = account.id
    email = account.login_email
    account_nick = (account.nickname or "").strip()
    scrub_tokens = [t for t in {email, account_nick} if t]

    members = list(
        db.scalars(
            select(RoomMember).where(RoomMember.account_id == account_id).with_for_update()
        ).all()
    )
    member_ids = [m.id for m in members]
    room_ids = {m.room_id for m in members}
    owned_room_ids = {m.room_id for m in members if m.room_role == "OWNER"}
    for m in members:
        nick = (m.nickname or "").strip()
        if nick:
            scrub_tokens.append(nick)

    if member_ids:
        for row in db.scalars(
            select(ScheduleResponseRange).where(
                ScheduleResponseRange.room_member_id.in_(member_ids)
            )
        ).all():
            db.delete(row)
        for row in db.scalars(
            select(ScheduleResponse).where(ScheduleResponse.room_member_id.in_(member_ids))
        ).all():
            db.delete(row)
        for row in db.scalars(
            select(ScheduleVote).where(ScheduleVote.room_member_id.in_(member_ids))
        ).all():
            db.delete(row)
        for row in db.scalars(
            select(ScheduleVoteBallot).where(
                ScheduleVoteBallot.room_member_id.in_(member_ids)
            )
        ).all():
            db.delete(row)
        # Legacy Conditional OK rows (unused by Potato Meet UI) — still purge PII.
        for row in db.scalars(
            select(AIDraft).where(AIDraft.room_member_id.in_(member_ids))
        ).all():
            db.delete(row)
        for row in db.scalars(
            select(Submission).where(Submission.room_member_id.in_(member_ids))
        ).all():
            db.delete(row)

    left_at = now()
    for member in members:
        member.nickname = ANONYMIZED_MEMBER_NICKNAME
        member.membership_status = "LEFT"
        member.left_at = left_at
        member.account_id = None
        member.token_hash = None
        member.request_key_hash = None
        member.request_hash = None
        if member.room_role == "OWNER":
            member.room_role = "MEMBER"

    for room in db.scalars(
        select(Room).where(Room.created_by_account_id == account_id).with_for_update()
    ).all():
        room.created_by_account_id = None
        room_ids.add(room.id)

    for room_id in owned_room_ids:
        room = db.get(Room, room_id)
        if room is None or room.progress_status == "deleted":
            continue
        successor = db.scalar(
            select(RoomMember)
            .where(
                RoomMember.room_id == room_id,
                RoomMember.membership_status == "ACTIVE",
            )
            .order_by(RoomMember.joined_at.asc())
            .with_for_update()
        )
        if successor is not None:
            successor.room_role = "OWNER"
            room.host_member_id = successor.id
        else:
            room.progress_status = "deleted"
            room.deleted_at = left_at
            room.revision = int(room.revision or 1) + 1

    if room_ids and scrub_tokens:
        for run in db.scalars(
            select(ScheduleRun).where(ScheduleRun.room_id.in_(room_ids))
        ).all():
            scrubbed = _scrub_text(run.ai_summary, scrub_tokens)
            if scrubbed != run.ai_summary:
                run.ai_summary = scrubbed
        for event in db.scalars(
            select(RoomEvent).where(RoomEvent.room_id.in_(room_ids))
        ).all():
            scrubbed = _scrub_text(event.message, scrub_tokens)
            if scrubbed != event.message:
                event.message = scrubbed or ANONYMIZED_MEMBER_NICKNAME

    for row in db.scalars(
        select(AccountSession).where(AccountSession.account_id == account_id)
    ).all():
        db.delete(row)

    for row in db.scalars(
        select(PasswordResetToken).where(PasswordResetToken.account_id == account_id)
    ).all():
        db.delete(row)

    for row in db.scalars(
        select(UserAuthChallenge).where(
            (UserAuthChallenge.account_id == account_id)
            | (UserAuthChallenge.email == email)
        )
    ).all():
        db.delete(row)


@router.delete("/me")
def delete_me(
    body: DeleteAccount,
    authorization: str | None = Header(default=None),
    db=Depends(db_session),
):
    """Hard-delete the authenticated USER account after password re-check.

    Leavers are anonymized; schedule availability/votes and legacy AI drafts for
    that membership are removed. OWNER rooms transfer to another ACTIVE member or
    soft-delete when empty. Other participants and confirmed results stay.
    """
    account = account_from_authorization(db, authorization)
    if account.account_type != "USER":
        fail(403, "사용할 수 없는 계정입니다.")
    try:
        valid = PASSWORDS.verify(account.password_hash, body.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not valid:
        fail(403, "비밀번호가 올바르지 않습니다.")

    _delete_account_side_effects(db, account)
    db.delete(account)
    return {"deleted": True}
