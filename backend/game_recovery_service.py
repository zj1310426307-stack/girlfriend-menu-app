"""Game reconnect credentials, active-room discovery and generic replay storage."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

import crud
import models
from core.cache import state_cache
from games.core.player import require_member
from user_service import ensure_user


def _hash(raw: str) -> str:
    """Hash a reconnect credential before persistent storage."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_token(db: Session, room_code: str, user_code: str) -> dict:
    """Rotate and return one 30-day room reconnect credential."""
    room = crud.get_game_room(db, room_code)
    require_member(db, room.id, user_code)
    user = ensure_user(db, user_code)
    raw = secrets.token_urlsafe(32)
    item = db.query(models.GameReconnectToken).filter(models.GameReconnectToken.room_id == room.id, models.GameReconnectToken.user_id == user.id).first()
    if not item:
        item = models.GameReconnectToken(room_id=room.id, user_id=user.id, token_hash=_hash(raw), expires_at=datetime.now() + timedelta(days=30))
        db.add(item)
    else:
        item.token_hash = _hash(raw); item.expires_at = datetime.now() + timedelta(days=30); item.revoked = False
    db.commit()
    return {"room_code": room.room_code, "game_type": room.game_type, "reconnect_token": raw, "expires_at": item.expires_at}


def verify_token(db: Session, raw: str) -> tuple[models.GameReconnectToken, models.User, models.GameRoom]:
    """Resolve a valid unexpired reconnect credential to its user and room."""
    item = db.query(models.GameReconnectToken).filter(models.GameReconnectToken.token_hash == _hash(raw), models.GameReconnectToken.revoked.is_(False), models.GameReconnectToken.expires_at > datetime.now()).first()
    if not item:
        raise HTTPException(status_code=401, detail="重连凭证无效或已过期")
    user = db.get(models.User, item.user_id); room = db.get(models.GameRoom, item.room_id)
    if not user or not room:
        raise HTTPException(status_code=404, detail="原游戏房间不存在")
    return item, user, room


def active_rooms(db: Session, user_code: str) -> list[dict]:
    """List unfinished rooms that the current device can continue."""
    rooms = db.query(models.GameRoom).join(models.GamePlayer, models.GamePlayer.room_id == models.GameRoom.id).filter(models.GamePlayer.player_id == user_code, models.GameRoom.status.in_(("waiting", "playing"))).order_by(models.GameRoom.created_at.desc()).limit(20).all()
    return [{"room_code": room.room_code, "game_type": room.game_type, "status": room.status, "created_at": room.created_at, "cached": bool(state_cache.get_game_state(room.room_code))} for room in rooms]


def save_replay(db: Session, record: models.GameRecord, state: dict) -> models.GameReplay:
    """Persist one generic replay snapshot idempotently for a completed record."""
    existing = db.query(models.GameReplay).filter(models.GameReplay.game_record_id == record.id).first()
    if existing:
        return existing
    moves = state.get("move_history") or state.get("play_history") or state.get("history") or []
    replay = models.GameReplay(game_record_id=record.id, game_type=record.game_type, moves=moves, final_state=state)
    db.add(replay); db.commit(); db.refresh(replay)
    return replay


def get_replay(db: Session, record_id: int, user_code: str) -> models.GameReplay:
    """Return a replay only to an original human room member."""
    record = db.get(models.GameRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="游戏记录不存在")
    require_member(db, record.room_id, user_code)
    replay = db.query(models.GameReplay).filter(models.GameReplay.game_record_id == record_id).first()
    if not replay:
        raise HTTPException(status_code=404, detail="该历史对局暂时没有完整回放")
    return replay
