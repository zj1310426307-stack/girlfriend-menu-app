"""Release readiness checks that depend on business-owned authentication state."""

from __future__ import annotations

import secrets

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth import is_password_hash_usable
from core.settings import load_settings
import models
from services.admin_auth_service import ADMIN_USERNAME


def _load_admin_account(db: Session) -> models.AdminAccount | None:
    """Read the database-owned admin identity without modifying login state."""
    return (
        db.query(models.AdminAccount)
        .filter(models.AdminAccount.username == ADMIN_USERNAME)
        .first()
    )


def authentication_readiness(db: Session) -> dict[str, str | list[str]]:
    """Report authentication release blockers without returning secret values."""
    settings = load_settings()
    missing: list[str] = []

    customer_invite = settings.customer_invite_code_value
    admin_invite = settings.admin_invite_code_value
    if not customer_invite:
        missing.append("CUSTOMER_INVITE_CODE")
    if not admin_invite:
        missing.append("ADMIN_INVITE_CODE")
    try:
        settings.require_admin_secret()
    except RuntimeError:
        missing.append("ADMIN_SECRET")

    try:
        account = _load_admin_account(db)
    except SQLAlchemyError:
        # A missing or incompatible auth table is a release blocker, not a
        # reason to expose database details through the readiness response.
        account = None
        missing.append("ADMIN_ACCOUNT_STORE")

    if account is not None:
        if not account.is_active:
            missing.append("ADMIN_ACCOUNT_ACTIVE")
        elif not is_password_hash_usable(account.password_hash):
            missing.append("ADMIN_ACCOUNT_PASSWORD_HASH")
    elif "ADMIN_ACCOUNT_STORE" not in missing:
        bootstrap_hash = settings.admin_password_hash_value
        if bootstrap_hash and not is_password_hash_usable(bootstrap_hash):
            missing.append("ADMIN_PASSWORD_HASH")
        elif not bootstrap_hash and not settings.admin_password_value:
            missing.append("ADMIN_PASSWORD_OR_HASH")

    if (
        settings.uses_managed_schema
        and customer_invite
        and admin_invite
        and secrets.compare_digest(customer_invite, admin_invite)
    ):
        missing.append("AUTH_INVITE_SEPARATION")

    return {
        "status": "release-blocked" if missing else "ready",
        "missing": sorted(set(missing)),
    }


__all__ = ["authentication_readiness"]
