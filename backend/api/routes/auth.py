"""Customer and administrator authentication routes."""

import secrets
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

import customer_service
import schemas
import user_service
from api.dependencies import (
    bearer_token,
    enforce_rate_limit,
    get_admin_invite_code,
    get_admin_password,
)
from auth import issue_admin_token
from database import get_db


router = APIRouter()


@router.post("/api/customers/session", response_model=schemas.CustomerSessionOut)
def create_customer_session(
    data: schemas.CustomerSessionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a rate-limited customer device session."""
    enforce_rate_limit(request, "customer-session", 8, 300)
    return customer_service.create_session(
        db,
        data.invite_code,
        data.display_name,
        data.device_label,
    )


@router.post("/api/customers/claim-legacy", response_model=schemas.CustomerSessionOut)
def claim_legacy_customer(
    data: schemas.CustomerLegacyClaim,
    request: Request,
    db: Session = Depends(get_db),
):
    """Retain the original one-time legacy claim contract for old clients."""
    enforce_rate_limit(request, "customer-claim", 5, 600)
    return customer_service.claim_legacy(
        db,
        data.invite_code,
        data.legacy_customer_id,
        data.display_name,
        data.device_label,
    )


@router.post("/api/customers/recover", response_model=schemas.CustomerSessionOut)
def recover_customer_session(
    data: schemas.CustomerRecovery,
    request: Request,
    db: Session = Depends(get_db),
):
    """Recover a stable legacy identity and rotate any bearer that may be lost."""
    enforce_rate_limit(request, "customer-recover", 5, 600)
    return customer_service.recover_legacy(
        db,
        data.invite_code,
        data.legacy_customer_id,
        data.display_name,
        data.device_label,
    )


@router.post("/api/customers/refresh", response_model=schemas.CustomerSessionOut)
def refresh_customer_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Rotate the caller's current authenticated customer session."""
    token = bearer_token(authorization)
    customer = customer_service.authenticate(db, token)
    return customer_service.refresh_session(db, customer, token or "")


@router.post("/api/customers/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_customer_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Revoke only the current customer bearer and preserve all owned history."""
    token = bearer_token(authorization)
    customer = customer_service.authenticate(db, token)
    customer_service.revoke_session(db, customer, token or "")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/admin/login", response_model=schemas.AdminLoginOut)
def admin_login(
    data: schemas.AdminLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate the administrator with the unchanged password and invite flow."""
    enforce_rate_limit(request, "admin-login", 60, 300)
    if not secrets.compare_digest(data.password, get_admin_password()):
        time.sleep(0.35)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理密码错误",
        )
    if not secrets.compare_digest(data.invite_code, get_admin_invite_code()):
        time.sleep(0.5)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邀请码错误",
        )
    user_service.ensure_user(db, "admin", "小厨房管理员", "ADMIN")
    token, expires_at = issue_admin_token()
    return {"token": token, "expires_at": expires_at}
