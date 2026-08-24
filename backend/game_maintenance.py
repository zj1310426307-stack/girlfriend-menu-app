"""Scheduled repair jobs for durable games and room lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session

import chess_service
from core.logging_privacy import opaque_log_reference
import crud
import flight_service
import models
from games.core.service import finalize_game_record, settle_session_game
from games.core.state import GameSessionStore
from games.animal.engine import AnimalGame
from games.chess.engine import ChessGame


logger = logging.getLogger(__name__)
MAX_SETTLEMENT_ATTEMPTS = 10


def _round_number(state: dict) -> int:
    return max(1, int(state.get("round") or 1))


def _record_for_state(
    db: Session,
    room: models.GameRoom,
    state: dict,
) -> models.GameRecord | None:
    return (
        db.query(models.GameRecord)
        .filter(
            models.GameRecord.room_id == room.id,
            models.GameRecord.round_number == _round_number(state),
        )
        .first()
    )


def _final_state(room: models.GameRoom, record: models.GameRecord) -> dict:
    """Recover the best available final state for a pending record."""
    if room.session and isinstance(room.session.state, dict):
        return dict(room.session.state)
    if room.state and isinstance(room.state.state, dict):
        snapshot = dict(room.state.state)
        completed = snapshot.get("completed_event") or {}
        result = completed.get("result") or {}
        return result.get("final_state") or result.get("state") or snapshot
    result = dict(record.result or {})
    return result.get("final_state") or result.get("state") or result


def _settle_room_state(
    db: Session,
    room: models.GameRoom,
    state: dict,
) -> models.GameRecord | None:
    """Dispatch one finished authoritative state to its owning finalizer."""
    if state.get("phase") != "finished":
        return None
    winner_id = state.get("winner_id")
    if room.game_type == "aeroplane":
        return flight_service._finish_if_needed(db, room, state)
    if room.game_type == "chinese_chess":
        chess_service._finish(db, room, state)
        return _record_for_state(db, room, state)
    if room.game_type in {"landlord", "jungle"}:
        return settle_session_game(
            db,
            room,
            state,
            winner_id,
            state.get("difficulty", "rule"),
        )

    record = _record_for_state(db, room, state)
    if not record:
        started_at = state.get("started_at")
        duration = 0
        try:
            duration = max(
                0,
                int(
                    (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(started_at)
                    ).total_seconds()
                ),
            )
        except (TypeError, ValueError):
            pass
        record = crud.finish_game_room(
            db,
            room.room_code,
            winner_id,
            duration,
            {"final_state": state, "_settlement": "pending"},
            _round_number(state),
        )
    return finalize_game_record(
        db,
        record,
        state,
        winner_id,
        state.get("difficulty", "rule"),
        include_mode_bonus=False,
    )


def reconcile_game_settlements(db: Session, limit: int = 50) -> dict:
    """Retry failed settlements and discover finished states missing a record."""
    repaired = 0
    failed = 0
    candidates = (
        db.query(models.GameRecord)
        .filter(
            models.GameRecord.settlement_status.in_(("pending", "failed")),
            models.GameRecord.settlement_attempts < MAX_SETTLEMENT_ATTEMPTS,
        )
        .order_by(models.GameRecord.created_at, models.GameRecord.id)
        .limit(limit)
        .all()
    )
    for record in candidates:
        room = record.room
        try:
            state = _final_state(room, record)
            if state.get("phase") != "finished":
                state = {
                    **state,
                    "phase": "finished",
                    "winner_id": record.winner,
                    "round": record.round_number,
                }
            _settle_room_state(db, room, state)
            repaired += 1
        except Exception as error:
            db.rollback()
            current = db.get(models.GameRecord, record.id)
            if current:
                current.settlement_status = "failed"
                current.settlement_error = str(error)[:1000]
                current.settlement_attempts = int(current.settlement_attempts or 0) + 1
                db.commit()
            failed += 1
            logger.error(
                "game_settlement_repair_failed record=%s error_type=%s",
                record.id,
                type(error).__name__,
            )

    remaining = max(0, limit - len(candidates))
    if remaining:
        sessions = (
            db.query(models.GameSession)
            .join(models.GameRoom, models.GameRoom.id == models.GameSession.room_id)
            .filter(models.GameRoom.status == "finished")
            .order_by(models.GameSession.updated_at)
            .limit(remaining)
            .all()
        )
        state_rows = (
            db.query(models.GameState)
            .join(models.GameRoom, models.GameRoom.id == models.GameState.room_id)
            .filter(models.GameRoom.status == "finished")
            .order_by(models.GameState.updated_at)
            .limit(remaining)
            .all()
        )
        for room, state in [
            *((item.room, dict(item.state or {})) for item in sessions),
            *((item.room, dict(item.state or {})) for item in state_rows),
        ]:
            completed = state.get("completed_event") or {}
            if completed:
                state = (
                    completed.get("result", {}).get("final_state")
                    or completed.get("result", {}).get("state")
                    or {
                        **completed.get("result", {}),
                        "phase": "finished",
                        "winner_id": completed.get("winner_id"),
                        "round": completed.get("round_number", 1),
                    }
                )
            if state.get("phase") != "finished" or _record_for_state(db, room, state):
                continue
            try:
                _settle_room_state(db, room, state)
                repaired += 1
            except Exception as error:
                db.rollback()
                failed += 1
                logger.error(
                    "missing_game_settlement_failed room_ref=%s error_type=%s",
                    opaque_log_reference("room", room.room_code),
                    type(error).__name__,
                )
    return {"repaired": repaired, "failed": failed}


def resolve_turn_timeouts(db: Session, limit: int = 100) -> dict:
    """Finish overdue Animal/Chinese-chess turns even when no client is polling."""
    finished = 0
    failed = 0
    sessions = (
        db.query(models.GameSession)
        .join(models.GameRoom, models.GameRoom.id == models.GameSession.room_id)
        .filter(
            models.GameRoom.status == "playing",
            models.GameSession.game_type.in_(("jungle", "chinese_chess")),
        )
        .order_by(models.GameSession.updated_at)
        .limit(limit)
        .all()
    )
    for session in sessions:
        room = session.room
        try:
            engine = (
                AnimalGame(session.state)
                if session.game_type == "jungle"
                else ChessGame(session.state)
            )
            if not engine.expire_turn():
                continue
            saved = GameSessionStore(db).save(
                session,
                engine.serialize(),
                session.version,
            )
            del saved
            if session.game_type == "chinese_chess":
                chess_service._persist_moves(db, room, engine.state)
                chess_service._finish(db, room, engine.state)
            else:
                settle_session_game(
                    db,
                    room,
                    engine.state,
                    engine.state.get("winner_id"),
                    engine.state.get("difficulty", "rule"),
                )
            finished += 1
        except Exception as error:
            db.rollback()
            failed += 1
            logger.error(
                "turn_timeout_settlement_failed room_ref=%s error_type=%s",
                opaque_log_reference("room", room.room_code),
                type(error).__name__,
            )
    return {"finished": finished, "failed": failed}
