"""Optimistically versioned storage for server-authoritative game sessions."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

import models
from core.cache import state_cache


class GameSessionStore:
    """Create, read and compare-and-swap V2.5 game session snapshots."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, room: models.GameRoom, state: dict) -> models.GameSession:
        """Persist the initial state exactly once for a room."""
        existing = self.get(room.id, required=False)
        if existing:
            return existing
        session = models.GameSession(
            room_id=room.id,
            game_type=room.game_type,
            current_turn=state.get("turn_id"),
            state=state,
            version=1,
            updated_at=datetime.now(),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        state_cache.set_game_state(room.room_code, {"game_type": room.game_type, "version": session.version, "state": state})
        return session

    def get(self, room_id: int, required: bool = True) -> models.GameSession | None:
        """Load one room session without mutating it."""
        session = (
            self.db.query(models.GameSession)
            .filter(models.GameSession.room_id == room_id)
            .first()
        )
        if required and not session:
            raise HTTPException(status_code=404, detail="游戏状态尚未建立")
        return session

    def save(self, session: models.GameSession, state: dict, expected_version: int) -> models.GameSession:
        """Atomically replace state only when the client version is still current."""
        if expected_version != session.version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "棋局已被另一端更新，请刷新后重试",
                    "current_version": session.version,
                },
            )
        new_version = session.version + 1
        result = self.db.execute(
            update(models.GameSession)
            .where(
                models.GameSession.id == session.id,
                models.GameSession.version == expected_version,
            )
            .values(
                state=state,
                current_turn=state.get("turn_id"),
                version=new_version,
                updated_at=datetime.now(),
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            latest = self.get(session.room_id)
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "棋局已被另一端更新，请刷新后重试",
                    "current_version": latest.version,
                },
            )
        self.db.commit()
        self.db.expire(session)
        self.db.refresh(session)
        room = self.db.get(models.GameRoom, session.room_id)
        if room:
            state_cache.set_game_state(room.room_code, {"game_type": room.game_type, "version": session.version, "state": state})
        return session
