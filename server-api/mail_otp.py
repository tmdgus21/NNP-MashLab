"""Shared SMTP delivery for one-time codes (admin + user auth).

Uses ADMIN_SMTP_* env vars already configured for the host. Does not log or
return the plaintext code.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def send_otp_email(
    email: str,
    code: str,
    *,
    subject: str,
    body: str | None = None,
) -> None:
    host = os.environ["ADMIN_SMTP_HOST"]
    message = EmailMessage()
    message["From"] = os.environ["ADMIN_SMTP_FROM"]
    message["To"] = email
    message["Subject"] = subject
    message.set_content(
        body
        or f"인증번호: {code}\n5분 안에 입력해 주세요. 요청하지 않았다면 무시하세요."
    )
    with smtplib.SMTP(host, int(os.getenv("ADMIN_SMTP_PORT", "587")), timeout=10) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(os.environ["ADMIN_SMTP_USER"], os.environ["ADMIN_SMTP_PASSWORD"])
        smtp.send_message(message)
