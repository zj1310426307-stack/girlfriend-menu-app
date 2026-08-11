"""Optimistically versioned storage for server-authoritative game sessions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import models
from core.cache import state_cache


@dataclass(frozen=True)
class ActionCommit:
    """Authoritative state returned for a new or replayed client action."""

    state: dict
    version: int
    updated_at: datetime
    replayed: bool


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
        crud.touch_game_room(room)
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
        room = self.db.get(models.GameRoom, session.room_id)
        if room:
            crud.touch_game_room(room)
        self.db.commit()
        self.db.expire(session)
        self.db.refresh(session)
        room = self.db.get(models.GameRoom, session.room_id)
        if room:
            state_cache.set_game_state(room.room_code, {"game_type": room.game_type, "version": session.version, "state": state})
        return session

    @staticmethod
    def _action_hash(action_type: str, payload: dict, expected_version: int) -> str:
        """Fingerprint request semantics so an ID cannot be reused for another move."""
        encoded = json.dumps(
            {
                "action": action_type,
                "payload": payload,
                "expected_version": expected_version,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _existing_action(
        self,
        room_id: int,
        player_id: str,
        client_action_id: str,
        request_hash: str,
    ) -> models.GameAction | None:
        """Load a receipt and reject conflicting reuse of its public identifier."""
        receipt = (
            self.db.query(models.GameAction)
            .filter(
                models.GameAction.room_id == room_id,
                models.GameAction.player_id == player_id,
                models.GameAction.client_action_id == client_action_id,
            )
            .first()
        )
        if receipt and receipt.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="动作编号已被另一项操作使用")
        return receipt

    def replay_action(
        self,
        room: models.GameRoom,
        player_id: str,
        client_action_id: str | None,
        action_type: str,
        payload: dict,
        expected_version: int,
    ) -> ActionCommit | None:
        """Return a prior response before the engine sees a duplicate request."""
        if not client_action_id:
            return None
        request_hash = self._action_hash(action_type, payload, expected_version)
        receipt = self._existing_action(
            room.id,
            player_id,
            client_action_id,
            request_hash,
        )
        if not receipt:
            return None
        return ActionCommit(
            deepcopy(receipt.response_state),
            receipt.response_version,
            receipt.created_at,
            True,
        )

    def save_action(
        self,
        session: models.GameSession,
        room: models.GameRoom,
        player_id: str,
        client_action_id: str | None,
        action_type: str,
        payload: dict,
        state: dict,
        expected_version: int,
    ) -> ActionCommit:
        """Commit a state transition and its idempotency receipt atomically.

        Old clients without ``client_action_id`` retain version-CAS behavior.
        New clients can safely resend the same request after a network timeout.
        """
        if not client_action_id:
            saved = self.save(session, state, expected_version)
            crud.touch_game_room(room)
            self.db.commit()
            return ActionCommit(deepcopy(saved.state), saved.version, saved.updated_at, False)

        request_hash = self._action_hash(action_type, payload, expected_version)
        existing = self._existing_action(
            room.id,
            player_id,
            client_action_id,
            request_hash,
        )
        if existing:
            return ActionCommit(
                deepcopy(existing.response_state),
                existing.response_version,
                existing.created_at,
                True,
            )
        if expected_version != session.version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "棋局已被另一端更新，请刷新后重试",
                    "current_version": session.version,
                },
            )

        new_version = session.version + 1
        updated_at = datetime.now(timezone.utc)
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
                updated_at=updated_at,
            )
        )
        if result.rowcount != 1:
            self.db.rollback()
            raced = self._existing_action(
                room.id,
                player_id,
                client_action_id,
                request_hash,
            )
            if raced:
                return ActionCommit(
                    deepcopy(raced.response_state),
                    raced.response_version,
                    raced.created_at,
                    True,
                )
            latest = self.get(session.room_id)
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "棋局已被另一端更新，请刷新后重试",
                    "current_version": latest.version,
                },
            )

        receipt = models.GameAction(
            room_id=room.id,
            player_id=player_id,
            client_action_id=client_action_id,
            action_type=action_type,
            request_hash=request_hash,
            request_version=expected_version,
            response_version=new_version,
            response_state=deepcopy(state),
            created_at=updated_at,
        )
        self.db.add(receipt)
        crud.touch_game_room(room, updated_at)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raced = self._existing_action(
                room.id,
                player_id,
                client_action_id,
                request_hash,
            )
            if not raced:
                raise
            return ActionCommit(
                deepcopy(raced.response_state),
                raced.response_version,
                raced.created_at,
                True,
            )
        state_cache.set_game_state(
            room.room_code,
            {"game_type": room.game_type, "version": new_version, "state": state},
        )
        return ActionCommit(deepcopy(state), new_version, updated_at, False)
