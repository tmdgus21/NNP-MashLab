"""Shared USER auth helpers for schedule/workflow tests (OTP challenge → verify)."""
from __future__ import annotations

import secrets
from unittest.mock import patch

from fastapi.testclient import TestClient


def register_verified(
    client: TestClient,
    *,
    email: str | None = None,
    password: str = "long-enough-password",
) -> dict:
    """Register a USER via OTP and return the verify JSON (includes token)."""
    email = email or f"u-{secrets.token_hex(4)}@example.test"
    codes: list[str] = []
    with patch(
        "user_auth.send_otp_email",
        side_effect=lambda _email, code, **_kwargs: codes.append(code),
    ):
        started = client.post(
            "/v1/auth/register",
            json={"email": email, "password": password},
        )
        if started.status_code != 201:
            raise AssertionError(f"register {started.status_code}: {started.text}")
        body = started.json()
        verified = client.post(
            "/v1/auth/register/verify",
            json={"challenge": body["challenge"], "code": codes[-1]},
        )
        if verified.status_code != 200:
            raise AssertionError(f"verify {verified.status_code}: {verified.text}")
        out = verified.json()
        out.setdefault("email", email)
        return out


def auth_headers(
    client: TestClient,
    *,
    email: str | None = None,
    password: str = "long-enough-password",
) -> dict[str, str]:
    """Bearer headers for a freshly registered USER."""
    token = register_verified(client, email=email, password=password)["token"]
    return {"Authorization": f"Bearer {token}"}
