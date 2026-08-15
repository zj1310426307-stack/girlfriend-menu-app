"""Shared authentication and request dependencies for every route group.

Keeping these functions in one module prevents subtly different token parsing,
legacy-header handling or rate-limit behavior after router modularization.
"""

import logging

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

import customer_service
import user_service
from auth import verify_admin_token_value
from core.cache import state_cache
from core.rate_limit import RateLimitExceeded, rate_limiter
from core.settings import load_settings
from database import get_db


logger = logging.getLogger(__name__)


def get_admin_password() -> str:
    """Return the configured administrator password or fail closed."""
    password = load_settings().admin_password_value
    if not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_PASSWORD",
        )
    return password


def get_admin_invite_code() -> str:
    """Return the administrator-only invite code or fail closed."""
    invite_code = load_settings().admin_invite_code_value
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_INVITE_CODE",
        )
    return invite_code


def verify_admin_token(authorization: str | None = Header(default=None)) -> None:
    """Require a valid administrator bearer token."""
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    if not verify_admin_token_value(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理登录已失效，请重新登录",
        )


def is_admin_token(token: str | None) -> bool:
    """Check an administrator token without raising an HTTP exception."""
    return verify_admin_token_value(token)


def allow_legacy_customer_header() -> bool:
    """Expose the deprecated customer header only in explicitly enabled environments."""
    return load_settings().allow_legacy_customer_header


def bearer_token(authorization: str | None) -> str | None:
    """Extract the opaque token from an HTTP Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return None


def get_optional_customer_id(
    authorization: str | None = Header(default=None),
    x_customer_id: str | None = Header(default=None, alias="X-Customer-Id"),
    db: Session = Depends(get_db),
) -> str | None:
    """Resolve one authenticated customer while preserving the development-only bridge."""
    token = bearer_token(authorization)
    if token:
        customer = customer_service.authenticate(db, token)
        user_service.ensure_user(db, customer.id, customer.display_name)
        state_cache.touch_presence(customer.id)
        return customer.id
    if allow_legacy_customer_header() and x_customer_id:
        value = x_customer_id.strip()[:100]
        if value:
            logger.warning("deprecated_customer_header path=unknown")
            user_service.ensure_user(db, value)
            return value
    return None


def get_customer_id(
    customer_id: str | None = Depends(get_optional_customer_id),
) -> str:
    """Return the server-authenticated device identity, never a client-selected ID."""
    if not customer_id:
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    return customer_id


def enforce_rate_limit(
    request: Request,
    scope: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Apply the shared per-IP rate limiter and normalize its public error response."""
    client = request.client.host if request.client else "unknown"
    try:
        rate_limiter.check(f"{scope}:{client}", limit, window_seconds)
    except RateLimitExceeded as error:
        raise HTTPException(status_code=429, detail="操作太频繁，请稍后再试") from error
