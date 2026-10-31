import os, secrets, hashlib, hmac, smtplib, ssl, ipaddress
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request
from sqlalchemy import select, update, delete
from database import now
from .models import Account, AdminSession, Audit, RateBucket, OTP

PASSWORDS = PasswordHasher()
COOKIE = '__Host-conditional-admin'
PREAUTH = '__Host-conditional-preauth'
def enabled(): return os.getenv('ADMIN_ENABLED') == '1'
def utc(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def secret():
    value = os.getenv('ADMIN_SECRET', '')
    if len(value) < 32: raise HTTPException(503, '관리자 보안 설정이 필요합니다.')
    return value
def mac(value): return hmac.new(secret().encode(), value.encode(), hashlib.sha256).hexdigest()
def log(db, actor, action, target='', reason='', data=None):
    db.add(Audit(actor=actor, action=action, target=target, reason=reason, data=data or {}))
def error(code, message): raise HTTPException(code, message)
def origin(request):
    if request.headers.get('origin') != os.getenv('ADMIN_ORIGIN', 'https://oranganman.site'):
        error(403, '요청 출처를 확인할 수 없습니다.')
def preauth(request):
    origin(request)
    token = request.cookies.get(PREAUTH, '')
    if not token or not hmac.compare_digest(token, request.headers.get('x-csrf-token', '')): error(403, '보안 토큰을 새로 받아 주세요.')
    try:
        stamp, nonce, signature = token.split('.')
        valid = hmac.compare_digest(mac(stamp + '.' + nonce), signature) and 0 <= now().timestamp() - int(stamp) < 600
    except (ValueError, TypeError): valid = False
    if not valid: error(403, '보안 토큰이 만료됐습니다.')
def rate(db, request, account=''):
    # Only configured proxy peers may supply Caddy's overwritten client-IP header.
    ip = request.client.host if request.client else 'unknown'
    try:
        peer = ipaddress.ip_address(ip)
        trusted = [ipaddress.ip_network(v.strip()) for v in os.getenv('ADMIN_TRUSTED_PROXY_CIDRS','').split(',') if v.strip()]
        if any(peer in network for network in trusted):
            ip = str(ipaddress.ip_address(request.headers.get('x-admin-client-ip', ip)))
    except ValueError:
        pass
    for name, limit in [('ip:' + ip, 120), ('account:' + account, 20)] if account else [('ip:' + ip, 120)]:
        key = digest(name)
        dialect = db.bind.dialect.name
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        insert = pg_insert if dialect == 'postgresql' else sqlite_insert
        db.execute(insert(RateBucket).values(key=key, count=0, reset=now()+timedelta(minutes=1)).on_conflict_do_nothing(index_elements=['key']))
        row = db.scalar(select(RateBucket).where(RateBucket.key == key).with_for_update())
        if utc(row.reset) <= now(): row.count, row.reset = 0, now()+timedelta(minutes=1)
        row.count += 1
        if row.count > limit: error(429, '요청이 너무 많습니다. 잠시 후 다시 시도하세요.')
    # Bound storage without deleting active buckets.
    db.execute(delete(RateBucket).where(RateBucket.reset < now()-timedelta(days=1)).execution_options(synchronize_session=False))
def revoke(db, account_id):
    db.execute(update(AdminSession).where(AdminSession.account_id == account_id).values(revoked=True))
    db.execute(update(OTP).where(OTP.account_id == account_id).values(used=True))
def failure(db, account, kind):
    account.failures += 1
    if account.failures >= 5:
        account.frozen = True
        revoke(db, account.id)
    log(db, account.id, kind, account.id, data={'failures': account.failures, 'frozen': account.frozen})
def authenticate(db, request, write=False, super_only=False):
    rate(db, request)
    token = request.cookies.get(COOKIE, '')
    row = db.get(AdminSession, digest(token)) if token else None
    if not row or row.revoked or utc(row.expires) <= now(): error(401, '관리자 로그인이 필요합니다.')
    account = db.scalar(select(Account).where(Account.id == row.account_id).with_for_update())
    db.refresh(row)
    if row.revoked or utc(row.expires) <= now(): error(401, '관리자 로그인이 필요합니다.')
    if not account or account.frozen or not account.approved: error(403, '사용할 수 없는 관리자 계정입니다.')
    if write:
        origin(request)
        if not hmac.compare_digest(row.csrf, request.headers.get('x-csrf-token', '')): error(403, '보안 토큰이 올바르지 않습니다.')
    if super_only and account.role != 'SUPER_ADMIN': error(403, '최고 관리자 권한이 필요합니다.')
    return account, row

def send_otp(email, code):
    host = os.environ['ADMIN_SMTP_HOST']
    message = EmailMessage()
    message['From'] = os.environ['ADMIN_SMTP_FROM']
    message['To'] = email
    message['Subject'] = '[조건부 OK] 관리자 로그인 인증번호'
    message.set_content(f'인증번호: {code}\n5분 안에 입력해 주세요. 요청하지 않았다면 관리자에게 문의하세요.')
    # No plaintext SMTP mode in production.
    with smtplib.SMTP(host, int(os.getenv('ADMIN_SMTP_PORT', '587')), timeout=10) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(os.environ['ADMIN_SMTP_USER'], os.environ['ADMIN_SMTP_PASSWORD'])
        smtp.send_message(message)
