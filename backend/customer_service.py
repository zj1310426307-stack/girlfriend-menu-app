"""Authenticated customer sessions and one-time migration of legacy device data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import secrets

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from auth import hash_token, new_customer_credentials
import models


DEFAULT_SESSION_TTL_DAYS = 90


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for all new session fields."""
    return datetime.now(timezone.utc)


def _session_ttl() -> timedelta:
    """Read a bounded session lifetime while keeping private-app defaults usable."""
    try:
        days = int(os.getenv("CUSTOMER_SESSION_TTL_DAYS", str(DEFAULT_SESSION_TTL_DAYS)))
    except ValueError:
        days = DEFAULT_SESSION_TTL_DAYS
    return timedelta(days=min(max(days, 1), 365))


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's occasionally naive DateTime values for safe comparison."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _device_label(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized[:100] or None


def _legacy_id(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 100:
        raise HTTPException(status_code=422, detail="旧设备标识格式不正确")
    return normalized


def verify_invite(invite_code: str) -> None:
    """Validate only the customer invite code; never fall back to admin secrets."""
    expected = os.getenv("CUSTOMER_INVITE_CODE")
    if not expected:
        raise HTTPException(status_code=503, detail="后端尚未配置 CUSTOMER_INVITE_CODE")
    if not secrets.compare_digest(invite_code, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邀请码不正确")


def _session_payload(
    customer: models.Customer,
    token: str,
    expires_at: datetime,
) -> dict:
    return {
        "customer_id": customer.id,
        "customer_token": token,
        "display_name": customer.display_name,
        "expires_at": expires_at,
    }


def _new_token() -> str:
    return f"gft_{secrets.token_urlsafe(48)}"


def _add_session(
    db: Session,
    customer: models.Customer,
    token: str,
    *,
    device_label: str | None = None,
    rotated_from_id: int | None = None,
) -> models.CustomerSession:
    """Attach one expiring token hash to a customer inside the caller transaction."""
    now = utc_now()
    session = models.CustomerSession(
        customer_id=customer.id,
        token_hash=hash_token(token),
        created_at=now,
        last_seen_at=now,
        expires_at=now + _session_ttl(),
        rotated_from_id=rotated_from_id,
        device_label=_device_label(device_label),
    )
    customer.token_hash = session.token_hash  # Temporary compatibility bridge for pre-2.12 clients.
    customer.updated_at = now
    customer.last_seen_at = now
    db.add(session)
    return session


def _rotate_all_sessions(
    db: Session,
    customer: models.Customer,
    *,
    device_label: str | None = None,
) -> dict:
    """Revoke every bearer for an identity and issue one recovery token atomically."""
    now = utc_now()
    latest = (
        db.query(models.CustomerSession)
        .filter(models.CustomerSession.customer_id == customer.id)
        .order_by(models.CustomerSession.id.desc())
        .first()
    )
    db.query(models.CustomerSession).filter(
        models.CustomerSession.customer_id == customer.id,
        models.CustomerSession.revoked_at.is_(None),
    ).update({models.CustomerSession.revoked_at: now}, synchronize_session=False)
    token = _new_token()
    new_session = _add_session(
        db,
        customer,
        token,
        device_label=device_label,
        rotated_from_id=latest.id if latest else None,
    )
    db.commit()
    return _session_payload(customer, token, new_session.expires_at)


def create_session(
    db: Session,
    invite_code: str,
    display_name: str,
    device_label: str | None = None,
) -> dict:
    """Create a new customer identity and its first expiring bearer session."""
    verify_invite(invite_code)
    for _ in range(5):
        customer_id, token = new_customer_credentials()
        if db.get(models.Customer, customer_id):
            continue
        customer = models.Customer(
            id=customer_id,
            token_hash=hash_token(token),
            display_name=display_name.strip() or "女朋友",
        )
        db.add(customer)
        db.flush()
        session = _add_session(db, customer, token, device_label=device_label)
        db.commit()
        return _session_payload(customer, token, session.expires_at)
    raise HTTPException(status_code=503, detail="暂时无法创建设备会话，请稍后重试")


def authenticate(
    db: Session,
    token: str | None,
    *,
    update_last_seen: bool = True,
) -> models.Customer:
    """Authenticate an active unexpired session, lazily bridging old token hashes.

    Latency-sensitive transports may skip the best-effort activity timestamp;
    every state-changing game action still persists its own room/player clock.
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请重新验证邀请码")
    token_digest = hash_token(token)
    now = utc_now()
    session = (
        db.query(models.CustomerSession)
        .options(joinedload(models.CustomerSession.customer))
        .filter(models.CustomerSession.token_hash == token_digest)
        .first()
    )
    if session:
        customer = session.customer
        expired = _as_utc(session.expires_at) <= now
        if not customer or not customer.is_active or session.revoked_at is not None or expired:
            if expired and session.revoked_at is None:
                session.revoked_at = now
                db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="设备登录已失效，请重新验证邀请码",
            )
        if update_last_seen:
            session.last_seen_at = now
            customer.last_seen_at = now
            db.commit()
        return customer

    # Compatibility bridge for databases upgraded before customer_sessions existed.
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.token_hash == token_digest, models.Customer.is_active.is_(True))
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="设备登录已失效，请重新验证邀请码",
        )
    legacy_session = models.CustomerSession(
        customer_id=customer.id,
        token_hash=token_digest,
        created_at=now,
        last_seen_at=now,
        expires_at=now + _session_ttl(),
        device_label="legacy-token",
    )
    customer.last_seen_at = now
    db.add(legacy_session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return authenticate(db, token)
    return customer


def refresh_session(
    db: Session,
    customer: models.Customer,
    current_token: str,
    device_label: str | None = None,
) -> dict:
    """Rotate the current bearer; the previous bearer becomes unusable immediately."""
    current = (
        db.query(models.CustomerSession)
        .filter(models.CustomerSession.token_hash == hash_token(current_token))
        .first()
    )
    if not current or current.customer_id != customer.id or current.revoked_at is not None:
        raise HTTPException(status_code=401, detail="设备登录已失效，请重新验证邀请码")
    current.revoked_at = utc_now()
    token = _new_token()
    new_session = _add_session(
        db,
        customer,
        token,
        device_label=device_label or current.device_label,
        rotated_from_id=current.id,
    )
    db.commit()
    return _session_payload(customer, token, new_session.expires_at)


def revoke_session(db: Session, customer: models.Customer, current_token: str) -> None:
    """Explicitly revoke the caller's current bearer without deleting identity history."""
    session = (
        db.query(models.CustomerSession)
        .filter(
            models.CustomerSession.customer_id == customer.id,
            models.CustomerSession.token_hash == hash_token(current_token),
        )
        .first()
    )
    if session and session.revoked_at is None:
        session.revoked_at = utc_now()
        customer.updated_at = utc_now()
        db.commit()


def _migrate_legacy_ownership(
    db: Session,
    legacy: str,
    customer_id: str,
    display_name: str,
) -> None:
    """Move legacy ownership in place; no history rows are copied or rebuilt."""
    mappings = (
        (models.Order, models.Order.customer_id),
        (models.FavoriteDish, models.FavoriteDish.customer_id),
        (models.LoveScore, models.LoveScore.customer_id),
        (models.DailyTask, models.DailyTask.customer_id),
        (models.GameMemory, models.GameMemory.customer_id),
        (models.UserAchievement, models.UserAchievement.customer_id),
        (models.GamePlayer, models.GamePlayer.player_id),
        (models.LoveTask, models.LoveTask.player_id),
        (models.GameEventLog, models.GameEventLog.player_id),
        (models.GameStatistic, models.GameStatistic.player_id),
        (models.ChessMove, models.ChessMove.player),
    )
    for model, column in mappings:
        db.query(model).filter(column == legacy).update({column: customer_id}, synchronize_session=False)
    db.query(models.GameRoom).filter(models.GameRoom.creator == legacy).update(
        {models.GameRoom.creator: customer_id}, synchronize_session=False
    )
    db.query(models.GameRecord).filter(models.GameRecord.winner == legacy).update(
        {models.GameRecord.winner: customer_id}, synchronize_session=False
    )
    db.query(models.ChessGame).filter(models.ChessGame.red_player == legacy).update(
        {models.ChessGame.red_player: customer_id}, synchronize_session=False
    )
    db.query(models.ChessGame).filter(models.ChessGame.black_player == legacy).update(
        {models.ChessGame.black_player: customer_id}, synchronize_session=False
    )
    db.query(models.ChessGame).filter(models.ChessGame.winner == legacy).update(
        {models.ChessGame.winner: customer_id}, synchronize_session=False
    )
    user = db.query(models.User).filter(models.User.user_code == legacy).first()
    if user:
        user.user_code = customer_id
        user.nickname = display_name.strip() or user.nickname


def _claim_new_legacy(
    db: Session,
    legacy: str,
    display_name: str,
    device_label: str | None,
) -> dict:
    customer_id, token = new_customer_credentials()
    customer = models.Customer(
        id=customer_id,
        token_hash=hash_token(token),
        display_name=display_name.strip() or "女朋友",
        legacy_customer_id=legacy,
    )
    db.add(customer)
    db.flush()
    session = _add_session(db, customer, token, device_label=device_label)
    _migrate_legacy_ownership(db, legacy, customer_id, display_name)
    db.commit()
    return _session_payload(customer, token, session.expires_at)


def claim_legacy(
    db: Session,
    invite_code: str,
    legacy_customer_id: str,
    display_name: str,
    device_label: str | None = None,
) -> dict:
    """Compatibility endpoint: first claim succeeds; repeated claims retain 409 semantics."""
    verify_invite(invite_code)
    legacy = _legacy_id(legacy_customer_id)
    if db.query(models.Customer).filter(models.Customer.legacy_customer_id == legacy).first():
        raise HTTPException(status_code=409, detail="这份旧数据已经被认领")
    return _claim_new_legacy(db, legacy, display_name, device_label)


def recover_legacy(
    db: Session,
    invite_code: str,
    legacy_customer_id: str,
    display_name: str,
    device_label: str | None = None,
) -> dict:
    """Recover one stable legacy identity and rotate all previously issued bearers."""
    verify_invite(invite_code)
    legacy = _legacy_id(legacy_customer_id)
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.legacy_customer_id == legacy)
        .first()
    )
    if customer:
        if not customer.is_active:
            raise HTTPException(status_code=403, detail="这台设备的身份已停用")
        customer.display_name = display_name.strip() or customer.display_name
        return _rotate_all_sessions(db, customer, device_label=device_label)

    try:
        return _claim_new_legacy(db, legacy, display_name, device_label)
    except IntegrityError:
        # A concurrent first recovery may win the unique legacy id race.
        db.rollback()
        customer = (
            db.query(models.Customer)
            .filter(models.Customer.legacy_customer_id == legacy)
            .first()
        )
        if not customer:
            raise HTTPException(status_code=503, detail="暂时无法恢复设备身份，请稍后重试")
        return _rotate_all_sessions(db, customer, device_label=device_label)
