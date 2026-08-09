"""Small dependency-free signing helpers for customer and admin credentials."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets


ADMIN_TOKEN_TTL = timedelta(hours=12)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_customer_credentials() -> tuple[str, str]:
    return f"gf_{secrets.token_urlsafe(18)}", f"gft_{secrets.token_urlsafe(48)}"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _admin_secret() -> str:
    secret = os.getenv("ADMIN_SECRET", "")
    if len(secret) < 16:
        raise RuntimeError("ADMIN_SECRET must contain at least 16 characters")
    return secret


def issue_admin_token() -> tuple[str, datetime]:
    issued_at = utc_now()
    expires_at = issued_at + ADMIN_TOKEN_TTL
    payload = {
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "role": "ADMIN",
        "ver": os.getenv("ADMIN_TOKEN_VERSION", "1"),
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64encode(hmac.new(_admin_secret().encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}", expires_at


def verify_admin_token_value(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64encode(
            hmac.new(_admin_secret().encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not secrets.compare_digest(signature, expected):
            return False
        payload = json.loads(_b64decode(encoded))
        return (
            payload.get("role") == "ADMIN"
            and payload.get("ver") == os.getenv("ADMIN_TOKEN_VERSION", "1")
            and int(payload.get("exp", 0)) > int(utc_now().timestamp())
            and int(payload.get("iat", 0)) <= int(utc_now().timestamp()) + 60
        )
    except (ValueError, TypeError, json.JSONDecodeError, RuntimeError):
        return False
