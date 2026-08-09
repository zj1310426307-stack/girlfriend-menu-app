"""Persistence and reward orchestration for the V2.4 couple flight game."""
from __future__ import annotations

from datetime import datetime
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

import crud
import models
from flight import FlightError, FlightGame, initial_state
from game_rewards import settle_game_rewards
from love_score import record_score
from core.cache import state_cache
from couple_profile_service import record_memory_once
from game_recovery_service import save_replay
from notification_service import create_notification


GAME_TYPE = "aeroplane"


def _validate_flight_room(room: models.GameRoom):
    if room.game_type != GAME_TYPE:
        raise HTTPException(status_code=409, detail="该房间不是飞行棋房间")


def _players(db: Session, room: models.GameRoom):
    return (
        db.query(models.GamePlayer)
        .filter(models.GamePlayer.room_id == room.id)
        .order_by(models.GamePlayer.seat)
        .all()
    )


def _payload(player: models.GamePlayer, name: str | None = None):
    return {
        "id": player.player_id,
        "name": (name or "").strip()[:20] or ("男朋友" if player.seat == 1 else "女朋友"),
        "seat": player.seat,
    }


def _state_row(db: Session, room: models.GameRoom, lock: bool = False):
    query = db.query(models.GameState).filter(models.GameState.room_id == room.id)
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        players = _players(db, room)
        row = models.GameState(
            room_id=room.id,
            game_type=GAME_TYPE,
            state=initial_state([_payload(player) for player in players]),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _response(room: models.GameRoom, row: models.GameState):
    return {
        "room_id": room.id,
        "room_code": room.room_code,
        "game_type": GAME_TYPE,
        "room_status": room.status,
        "state": row.state,
        "updated_at": row.updated_at,
    }


def _cache(room: models.GameRoom, state: dict) -> None:
    """Mirror the durable board to Redis without making Redis authoritative."""
    state_cache.set_game_state(
        room.room_code,
        {"game_type": GAME_TYPE, "version": 1, "state": state},
    )


def create_room(db: Session, creator_id: str, player_name: str):
    room = crud.create_game_room(db, GAME_TYPE, creator_id)
    player = crud.join_game_room(db, room.room_code, creator_id)
    row = models.GameState(
        room_id=room.id,
        game_type=GAME_TYPE,
        state=initial_state([_payload(player, player_name)]),
    )
    db.add(row)
    db.commit()
    db.refresh(room)
    db.refresh(row)
    _cache(room, row.state)
    return _response(room, row)


def join_room(db: Session, room_code: str, player_id: str, player_name: str):
    room = crud.get_game_room(db, room_code)
    _validate_flight_room(room)
    player = crud.join_game_room(db, room.room_code, player_id)
    row = _state_row(db, room, lock=True)
    game = FlightGame(row.state)
    known_names = {item["id"]: item["name"] for item in game.state["players"]}
    known_names[player_id] = player_name
    game.sync_players(
        [_payload(item, known_names.get(item.player_id)) for item in _players(db, room)]
    )
    row.state = game.serialize()
    row.updated_at = datetime.now()
    if game.state["phase"] == "playing":
        room.status = "playing"
        room.finished_at = None
    db.commit()
    db.refresh(room)
    db.refresh(row)
    _cache(room, row.state)
    return _response(room, row)


def get_state(db: Session, room_code: str, player_id: str):
    room = crud.get_game_room(db, room_code)
    _validate_flight_room(room)
    if not any(player.player_id == player_id for player in _players(db, room)):
        raise HTTPException(status_code=403, detail="你还没有加入这个房间")
    row = _state_row(db, room)
    return _response(room, row)


def _pick_event(db: Session, event_type: str):
    candidates = (
        db.query(models.GameEvent)
        .filter(models.GameEvent.type == event_type, models.GameEvent.enabled.is_(True))
        .all()
    )
    if candidates:
        return secrets.choice(candidates)
    fallback = models.GameEvent(
        type=event_type,
        content="和对方完成一次温暖的小互动",
        score=3,
        enabled=True,
    )
    db.add(fallback)
    db.flush()
    return fallback


def _attach_random_event(db: Session, room: models.GameRoom, game: FlightGame):
    pending = game.state.get("pending_event")
    if not pending or pending.get("log_id"):
        return None
    event = _pick_event(db, pending["type"])
    log = models.GameEventLog(
        room_id=room.id,
        event_id=event.id,
        player_id=pending["player_id"],
        content=event.content,
        score=event.score,
        status="pending",
    )
    db.add(log)
    db.flush()
    game.attach_event(
        {
            "log_id": log.id,
            "content": log.content,
            "score": log.score,
        }
    )
    return log


def _duration(state: dict) -> int:
    raw = state.get("started_at")
    if not raw:
        return 0
    try:
        return max(0, int((datetime.now() - datetime.fromisoformat(raw)).total_seconds()))
    except (TypeError, ValueError):
        return 0


def _finish_if_needed(db: Session, room: models.GameRoom, state: dict):
    if state.get("phase") != "finished":
        return None
    existing = (
        db.query(models.GameRecord)
        .filter(
            models.GameRecord.room_id == room.id,
            models.GameRecord.round_number == state.get("round", 1),
        )
        .first()
    )
    if existing and (existing.result or {}).get("_settlement") == "complete":
        return existing
    record = crud.finish_game_room(
        db,
        room.room_code,
        state.get("winner_id"),
        _duration(state),
        {"state": state, "_settlement": "pending"},
        state.get("round", 1),
    )
    settle_game_rewards(
        db,
        record,
        [player.player_id for player in record.players],
        state.get("winner_id"),
    )
    human_ids = [player.player_id for player in record.players]
    for player_id in human_ids:
        record_memory_once(
            db,
            player_id,
            "GAME",
            "一起完成了一局飞行棋",
            f"在第 {record.round_number} 局留下了一段互动时光。",
            "GAME_RECORD",
            record.id,
            record.created_at.date(),
        )
        create_notification(
            db,
            player_id,
            "GAME_FINISHED",
            "飞行棋对局结束啦",
            "回到一起玩，可以查看战绩和继续下一局。",
            record.id,
        )
    save_replay(db, record, state)
    record.result = {**(record.result or {}), "_settlement": "complete"}
    db.commit()
    return record


def perform_action(
    db: Session,
    room_code: str,
    player_id: str,
    action: str,
    piece_index: int | None = None,
):
    room = crud.get_game_room(db, room_code)
    _validate_flight_room(room)
    if not any(player.player_id == player_id for player in _players(db, room)):
        raise HTTPException(status_code=403, detail="你还没有加入这个房间")
    row = _state_row(db, room, lock=True)
    game = FlightGame(row.state)
    completed_log = None
    try:
        if action == "ROLL_DICE":
            game.roll_dice(player_id, secrets.randbelow(6) + 1)
        elif action == "MOVE_PIECE":
            if piece_index is None:
                raise HTTPException(status_code=422, detail="请选择要移动的棋子")
            game.move_piece(player_id, piece_index)
            _attach_random_event(db, room, game)
        elif action == "COMPLETE_EVENT":
            pending = game.state.get("pending_event") or {}
            log_id = pending.get("log_id")
            if not log_id:
                raise HTTPException(status_code=409, detail="当前没有待完成的互动事件")
            completed_log = (
                db.query(models.GameEventLog)
                .filter(
                    models.GameEventLog.id == log_id,
                    models.GameEventLog.room_id == room.id,
                    models.GameEventLog.player_id == player_id,
                )
                .first()
            )
            if not completed_log:
                raise HTTPException(status_code=404, detail="互动记录不存在")
            game.complete_event(player_id)
            completed_log.status = "completed"
            completed_log.completed_at = datetime.now()
        else:
            raise HTTPException(status_code=422, detail="不支持的飞行棋动作")
    except FlightError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    row.state = game.serialize()
    row.updated_at = datetime.now()
    if completed_log:
        record_score(
            db,
            player_id,
            "GAME_EVENT",
            completed_log.score,
            f"完成飞行棋互动：{completed_log.content}",
            completed_log.id,
        )
    db.commit()
    db.refresh(row)
    _finish_if_needed(db, room, row.state)
    _cache(room, row.state)
    db.refresh(room)
    db.refresh(row)
    return _response(room, row)
