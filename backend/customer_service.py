"""Authenticated device sessions and one-time migration of legacy device data."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from auth import hash_token, new_customer_credentials
import models


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def verify_invite(invite_code: str) -> None:
    expected = os.getenv("CUSTOMER_INVITE_CODE") or os.getenv("ADMIN_INVITE_CODE")
    if not expected:
        raise HTTPException(status_code=503, detail="后端尚未配置 CUSTOMER_INVITE_CODE")
    if not secrets.compare_digest(invite_code, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邀请码不正确")


def _session_payload(customer: models.Customer, token: str) -> dict:
    return {
        "customer_id": customer.id,
        "customer_token": token,
        "display_name": customer.display_name,
        "expires_at": None,
    }


def create_session(db: Session, invite_code: str, display_name: str) -> dict:
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
        db.commit()
        return _session_payload(customer, token)
    raise HTTPException(status_code=503, detail="暂时无法创建设备会话，请稍后重试")


def authenticate(db: Session, token: str | None) -> models.Customer:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请重新验证邀请码")
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.token_hash == hash_token(token), models.Customer.is_active.is_(True))
        .first()
    )
    if not customer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="设备登录已失效，请重新验证邀请码")
    customer.last_seen_at = utc_now()
    db.commit()
    return customer


def refresh_session(db: Session, customer: models.Customer) -> dict:
    token = f"gft_{secrets.token_urlsafe(48)}"
    customer.token_hash = hash_token(token)
    customer.updated_at = utc_now()
    customer.last_seen_at = utc_now()
    db.commit()
    return _session_payload(customer, token)


def claim_legacy(db: Session, invite_code: str, legacy_customer_id: str, display_name: str) -> dict:
    verify_invite(invite_code)
    legacy = legacy_customer_id.strip()
    if not legacy or len(legacy) > 100:
        raise HTTPException(status_code=422, detail="旧设备标识格式不正确")
    if db.query(models.Customer).filter(models.Customer.legacy_customer_id == legacy).first():
        raise HTTPException(status_code=409, detail="这份旧数据已经被认领")

    customer_id, token = new_customer_credentials()
    customer = models.Customer(
        id=customer_id,
        token_hash=hash_token(token),
        display_name=display_name.strip() or "女朋友",
        legacy_customer_id=legacy,
    )
    db.add(customer)
    db.flush()

    # These updates preserve ownership instead of copying or rebuilding history.
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
    db.commit()
    return _session_payload(customer, token)
