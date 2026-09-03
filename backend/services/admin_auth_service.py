"""Database-owned administrator authentication and append-only audit events."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from auth import hash_password, verify_password
from core.settings import load_settings
import models


ADMIN_USERNAME = "admin"


def _record(db: Session, account: models.AdminAccount | None, outcome: str) -> None:
    """Commit one minimal event without storing passwords, invites, tokens, or IPs."""
    db.add(models.AdminAuthEvent(
        admin_id=account.id if account else None,
        username=ADMIN_USERNAME,
        outcome=outcome,
    ))
    db.commit()


def _bootstrap_password_matches(password: str) -> bool | None:
    """Verify the one-time environment bootstrap credential in either safe form."""
    settings = load_settings()
    if settings.admin_password_hash_value:
        return verify_password(password, settings.admin_password_hash_value)
    if settings.admin_password_value:
        return secrets.compare_digest(password, settings.admin_password_value)
    return None


def authenticate(db: Session, password: str, invite_code: str) -> models.AdminAccount:
    """Verify the database hash, bootstrapping it once from legacy configuration."""
    account = (
        db.query(models.AdminAccount)
        .filter(models.AdminAccount.username == ADMIN_USERNAME)
        .first()
    )
    password_valid = verify_password(password, account.password_hash) if account else False
    rotated_from_config = False
    configured_match = None
    if not password_valid:
        configured_match = _bootstrap_password_matches(password)
        if account and configured_match:
            password_valid = True
            rotated_from_config = True
        elif not account:
            password_valid = bool(configured_match)
    if not account and configured_match is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_PASSWORD 或 ADMIN_PASSWORD_HASH",
        )
    if not password_valid:
        _record(db, account, "PASSWORD_FAILED")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理密码错误",
        )
    settings = load_settings()
    expected_invite = settings.admin_invite_code_value
    if not expected_invite:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="后端尚未配置 ADMIN_INVITE_CODE",
        )
    if not secrets.compare_digest(invite_code, expected_invite):
        _record(db, account, "INVITE_FAILED")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邀请码错误",
        )
    if account and not account.is_active:
        _record(db, account, "ACCOUNT_DISABLED")
        raise HTTPException(status_code=403, detail="管理账号已停用")
    if account and rotated_from_config:
        # Persist a configured rotation only after every authentication factor
        # and the account state have succeeded in the same transaction.
        account.password_hash = hash_password(password)
    if not account:
        account = models.AdminAccount(
            username=ADMIN_USERNAME,
            password_hash=hash_password(password),
            role="ADMIN",
        )
        db.add(account)
        db.flush()
    account.last_login_at = models.utc_now()
    db.add(models.AdminAuthEvent(
        admin=account,
        username=ADMIN_USERNAME,
        outcome="SUCCESS_CONFIG_ROTATION" if rotated_from_config else "SUCCESS",
    ))
    db.commit()
    return account


__all__ = ["ADMIN_USERNAME", "authenticate"]
