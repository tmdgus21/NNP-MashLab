"""Email USER signup/login — separate from admin OTP and from GUEST meeting placeholders."""
import hashlib
import re
import secrets
from datetime import timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from database import session
from models import Account, AccountSession, now


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


def db_session():
    with session() as db, db.begin():
        yield db


def fail(status: int, message: str):
    raise HTTPException(status, detail=message)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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


@router.post("/register", status_code=201)
def register(body: Register, db=Depends(db_session, scope="function")):
    email = validate_email(body.email)
    if len(body.password) < 12:
        fail(422, "비밀번호는 12자 이상이어야 합니다.")
    existing = db.scalar(select(Account.id).where(Account.login_email == email))
    if existing:
        fail(409, "이미 등록된 이메일입니다.")
    account = Account(
        login_email=email,
        password_hash=PASSWORDS.hash(body.password),
        account_type="USER",
        account_status="ACTIVE",
        approved=True,
    )
    db.add(account)
    db.flush()
    token, _ = issue_session(db, account)
    return {"accountId": account.id, "email": account.login_email, "token": token}


@router.post("/login")
def login(body: Login, db=Depends(db_session, scope="function")):
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
    token, _ = issue_session(db, account)
    return {"accountId": account.id, "email": account.login_email, "token": token}


@router.get("/me")
def me(authorization: str | None = Header(default=None), db=Depends(db_session, scope="function")):
    account = account_from_authorization(db, authorization)
    return {"accountId": account.id, "email": account.login_email, "accountType": account.account_type}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db=Depends(db_session, scope="function")):
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
