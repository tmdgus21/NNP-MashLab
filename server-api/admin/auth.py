import secrets
from datetime import timedelta
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from database import session, now
from .models import Account, OTP, AdminSession
from . import security as sec
router = APIRouter(prefix='/admin-api/auth', tags=['Admin authentication'])

def db_session():
    if not sec.enabled(): raise HTTPException(404, '관리자 기능이 활성화되지 않았습니다.')
    with session() as db:
        try:
            yield db
            db.commit()
        except HTTPException as exc:
            # Authentication failures and lockout counters must survive a 4xx response.
            sec.log(db, 'request', 'request.denied', reason=str(exc.status_code))
            db.commit()
            raise
        except Exception:
            db.rollback()
            raise
class Input(BaseModel): model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
class Login(Input):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
class Verify(Input):
    challenge: str = Field(min_length=32, max_length=64)
    code: str = Field(pattern=r'^\d{6}$')
class Resend(Input): challenge: str = Field(min_length=32, max_length=64)

def account_for(db, challenge):
    otp = db.scalar(select(OTP).where(OTP.challenge == challenge))
    if not otp: sec.error(401, '인증 요청이 올바르지 않습니다.')
    account = db.scalar(select(Account).where(Account.id == otp.account_id).with_for_update())
    db.refresh(otp)
    if otp.challenge != challenge: sec.error(401, '인증 요청이 변경되었습니다. 다시 로그인하세요.')
    if account.frozen or not account.approved: sec.error(403, '관리자 계정이 동결되었거나 승인되지 않았습니다.')
    return account, otp

def issue(db, account):
    previous = db.get(OTP, account.id)
    if previous and sec.utc(previous.sent)+timedelta(seconds=60) > now(): sec.error(429, '인증번호 재발송은 60초 후 가능합니다.')
    challenge, code = secrets.token_urlsafe(32), f'{secrets.randbelow(1000000):06d}'
    try: sec.send_otp(account.email, code)
    except Exception:
        sec.log(db, account.id, 'otp.delivery_failed', account.id)
        sec.error(503, '인증 메일을 보내지 못했습니다. 잠시 후 다시 시도하세요.')
    otp = previous or OTP(account_id=account.id)
    otp.challenge, otp.digest, otp.expires, otp.sent, otp.used = challenge, sec.mac(challenge+':'+code), now()+timedelta(minutes=5), now(), False
    db.add(otp)
    sec.log(db, account.id, 'otp.sent', account.id)
    return {'challenge':challenge,'expiresIn':300,'resendAfter':60}

@router.get('/csrf')
def csrf(request: Request, db=Depends(db_session)):
    sec.rate(db, request)
    value = f'{int(now().timestamp())}.{secrets.token_urlsafe(24)}'
    token = value+'.'+sec.mac(value)
    response = JSONResponse({'csrf':token})
    response.set_cookie(sec.PREAUTH, token, secure=True, httponly=True, samesite='strict', path='/')
    response.headers['Cache-Control'] = 'no-store'
    return response

@router.post('/login')
def login(body: Login, request: Request, db=Depends(db_session)):
    sec.preauth(request)
    email = body.email.strip().lower()
    sec.rate(db, request, email)
    account = db.scalar(select(Account).where(Account.email == email).with_for_update())
    if account and (account.frozen or not account.approved): sec.error(403, '관리자 계정이 동결되었거나 승인되지 않았습니다.')
    valid = False
    if account:
        try: valid = sec.PASSWORDS.verify(account.password_hash, body.password)
        except (sec.VerificationError, sec.InvalidHashError): pass
    else:
        # Match expensive work; never reveal whether an unregistered email exists.
        sec.PASSWORDS.hash(body.password)
    if not valid:
        if account: sec.failure(db, account, 'password.failed')
        sec.error(401, '이메일 또는 비밀번호를 확인하세요.')
    # Correct password does NOT reset accumulated failures or issue a session.
    return issue(db, account)

@router.post('/resend')
def resend(body: Resend, request: Request, db=Depends(db_session)):
    sec.preauth(request)
    sec.rate(db, request, body.challenge)
    account, otp = account_for(db, body.challenge)
    if otp.used or sec.utc(otp.expires) < now(): sec.error(401, '다시 로그인해 주세요.')
    return issue(db, account)

@router.post('/verify')
def verify(body: Verify, request: Request, db=Depends(db_session)):
    sec.preauth(request)
    sec.rate(db, request, body.challenge)
    account, otp = account_for(db, body.challenge)
    if otp.used or sec.utc(otp.expires) <= now() or not secrets.compare_digest(otp.digest, sec.mac(body.challenge+':'+body.code)):
        sec.failure(db, account, 'otp.failed')
        sec.error(401, '인증번호가 올바르지 않거나 만료됐습니다.')
    otp.used, account.failures = True, 0
    token = secrets.token_urlsafe(48)
    row = AdminSession(digest=sec.digest(token), account_id=account.id, csrf=secrets.token_urlsafe(32), expires=now()+timedelta(hours=8))
    db.add(row)
    sec.log(db, account.id, 'login.success', account.id)
    response = JSONResponse({'email':account.email,'role':account.role,'csrf':row.csrf,'expiresAt':row.expires.isoformat()})
    response.set_cookie(sec.COOKIE, token, secure=True, httponly=True, samesite='strict', path='/')
    response.delete_cookie(sec.PREAUTH, secure=True, httponly=True, samesite='strict', path='/')
    return response

@router.get('/me')
def me(request: Request, db=Depends(db_session)):
    account, row = sec.authenticate(db, request)
    return {'id':account.id,'email':account.email,'role':account.role,'csrf':row.csrf,'expiresAt':sec.utc(row.expires).isoformat()}

@router.post('/logout')
def logout(request: Request, db=Depends(db_session)):
    account, row = sec.authenticate(db, request, write=True)
    row.revoked = True
    sec.log(db, account.id, 'logout', account.id)
    response = JSONResponse({'ok':True})
    response.delete_cookie(sec.COOKIE, secure=True, httponly=True, samesite='strict', path='/')
    return response
