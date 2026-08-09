"""Backward-compatible unified identity service."""
from sqlalchemy.orm import Session

import models


def ensure_user(db: Session, user_code: str, nickname: str | None = None, role: str = "CUSTOMER") -> models.User:
    """Map an existing customer/game code to one durable user without changing it."""
    code = (user_code or "").strip()
    user = db.query(models.User).filter(models.User.user_code == code).first()
    if user:
        if nickname and user.nickname == "用户":
            user.nickname = nickname[:50]
            db.commit()
            db.refresh(user)
        return user
    user = models.User(user_code=code, nickname=(nickname or "用户")[:50], role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_system_users(db: Session) -> None:
    """Ensure stable admin and AI identities exist for notifications and analytics."""
    ensure_user(db, "admin", "小厨房管理员", "ADMIN")
    for code, name in (("ai_landlord", "斗地主 AI"), ("ai_animal", "斗兽棋 AI"), ("ai_chess", "象棋 AI")):
        ensure_user(db, code, name, "AI")
