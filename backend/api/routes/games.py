"""HTTP game lobby, recovery, room and action routes.

This module is intentionally a presentation-only move from ``main.py``; game
state transitions, settlement and AI behavior remain in their existing services.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import achievement_service
import animal_service
import chess_service
import flight_service
import game_data_service
import game_recovery_service
import landlord_service
import schemas
from api.dependencies import (
    allow_legacy_customer_header,
    get_admin_invite_code,
    get_customer_id,
    get_optional_customer_id,
)
from core.cache import state_cache
from database import get_db
from game_runtime import game_room_manager
from services import game_persistence_service


router = APIRouter()


def _legacy_invite_allowed(invite_code: str) -> bool:
    """Preserve the development-only legacy invite comparison in one place."""
    return secrets.compare_digest(invite_code, get_admin_invite_code())


@router.get("/api/games", response_model=list[schemas.GameOut])
def games(db: Session = Depends(get_db)):
    """Return the existing game catalogue."""
    return game_persistence_service.list_games(db)


@router.get("/api/games/records/my", response_model=list[schemas.GameRecordOut])
def my_game_records(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return game records visible to the authenticated customer."""
    return game_persistence_service.list_game_records(db, customer_id)


@router.get("/api/games/active", response_model=list[schemas.ActiveGameOut])
def active_games(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Discover unfinished rooms after a page or process restart."""
    return game_recovery_service.active_rooms(db, customer_id)


@router.post("/api/games/reconnect/token", response_model=schemas.ReconnectTokenOut)
def create_reconnect_token(
    data: schemas.ReconnectTokenRequest,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Issue the existing hashed reconnect token for an owned room."""
    return game_recovery_service.issue_token(db, data.room_code, customer_id)


@router.post("/api/games/reconnect")
async def reconnect_game(
    data: schemas.ReconnectRequest,
    db: Session = Depends(get_db),
):
    """Resume a room from a hashed token and its authoritative durable state."""
    _, user, room = game_recovery_service.verify_token(db, data.reconnect_token)
    state_cache.touch_presence(user.user_code)
    if room.game_type == "aeroplane":
        payload = flight_service.get_state(db, room.room_code, user.user_code)
    elif room.game_type in {"landlord", "animal", "chinese_chess"}:
        payload = animal_service.get_any_state(db, room.room_code, user.user_code)
    elif room.game_type in {"dice", "gomoku"}:
        await game_room_manager.ensure_room(
            room.room_code,
            room.game_type,
            room.max_players,
        )
        await game_room_manager.restore_players(
            room.room_code,
            game_persistence_service.list_game_players(db, room.room_code),
        )
        payload = await game_room_manager.recovery_state(
            room.room_code,
            user.user_code,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="游戏状态暂时无法恢复")
    else:
        payload = {
            "room_code": room.room_code,
            "game_type": room.game_type,
            "room_status": room.status,
            "reconnect_required": True,
        }
    return {"room_code": room.room_code, "game_type": room.game_type, "state": payload}


@router.get(
    "/api/games/records/{record_id}/replay",
    response_model=schemas.GameReplayOut,
)
def game_replay(
    record_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return one member-authorized durable replay."""
    return game_recovery_service.get_replay(db, record_id, customer_id)


@router.post(
    "/api/games/rooms",
    response_model=schemas.GameRoomOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_game_room(
    data: schemas.GameRoomCreate,
    customer_id: str | None = Depends(get_optional_customer_id),
    db: Session = Depends(get_db),
):
    """Create a unified real-time room without altering game initialization."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    creator = customer_id or (data.creator if allow_legacy_customer_header() else None)
    if not creator:
        raise HTTPException(status_code=401, detail="请先用邀请码验证设备")
    room = game_persistence_service.create_game_room(db, data.game_type, creator)
    if data.game_type == "gomoku" and data.mode == "ai":
        game_persistence_service.join_game_room(db, room.room_code, creator)
        game_persistence_service.join_game_room(db, room.room_code, "ai_gomoku")
    await game_room_manager.ensure_room(room.room_code, room.game_type, room.max_players)
    await game_room_manager.restore_players(
        room.room_code,
        game_persistence_service.list_game_players(db, room.room_code),
    )
    if data.game_type == "gomoku" and data.mode == "ai":
        await game_room_manager.configure_gomoku_ai(room.room_code, data.difficulty)
    db.refresh(room)
    return room


@router.get("/api/games/rooms/{room_code}", response_model=schemas.GameRoomOut)
def game_room_detail(room_code: str, db: Session = Depends(get_db)):
    """Return persistent metadata for one room."""
    return game_persistence_service.get_game_room(db, room_code)


@router.post(
    "/api/games/flight/create",
    response_model=schemas.FlightStateOut,
    status_code=status.HTTP_201_CREATED,
)
def create_flight_room(
    data: schemas.FlightRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create a flight-chess room through the existing authoritative service."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return flight_service.create_room(
        db,
        customer_id,
        data.player_name,
        data.mode,
        data.difficulty,
    )


@router.post("/api/games/flight/join", response_model=schemas.FlightStateOut)
def join_flight_room(
    data: schemas.FlightRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Join the second flight-chess seat."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return flight_service.join_room(db, data.room_code, customer_id, data.player_name)


@router.get("/api/games/flight/{room_code}/state", response_model=schemas.FlightStateOut)
def flight_room_state(
    room_code: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return viewer-filtered flight-chess state."""
    return flight_service.get_state(db, room_code, customer_id)


@router.post("/api/games/flight/action", response_model=schemas.FlightStateOut)
def flight_room_action(
    data: schemas.FlightAction,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Forward a versioned flight-chess action to the existing service."""
    return flight_service.perform_action(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.piece_index,
        data.expected_version,
        data.client_action_id,
    )


@router.post(
    "/api/games/landlord/create",
    response_model=schemas.GameSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_landlord_room(
    data: schemas.LandlordRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create the first human seat in a two-human-plus-AI landlord room."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return landlord_service.create(
        db,
        customer_id,
        data.player_name,
        data.difficulty,
        data.mode,
    )


@router.post("/api/games/landlord/join", response_model=schemas.GameSessionOut)
def join_landlord_room(
    data: schemas.LandlordRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Join the second human seat and trigger server-side dealing."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return landlord_service.join_room(db, data.room_code, customer_id, data.player_name)


@router.post("/api/games/landlord/action", response_model=schemas.GameSessionOut)
def landlord_action(
    data: schemas.LandlordAction,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Apply bidding, card-play, pass or chat through the authoritative engine."""
    return landlord_service.action(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.model_dump(
            exclude={"room_code", "action", "expected_version", "client_action_id"}
        ),
        data.expected_version,
        data.client_action_id,
    )


@router.post(
    "/api/games/animal/create",
    response_model=schemas.GameSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_animal_room(
    data: schemas.AnimalRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create couple or AI Animal Chess using the same room platform."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return animal_service.create(
        db,
        customer_id,
        data.player_name,
        data.mode,
        data.difficulty,
    )


@router.post("/api/games/animal/join", response_model=schemas.GameSessionOut)
def join_animal_room(
    data: schemas.AnimalRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Join the second seat in a couple Animal Chess room."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return animal_service.join_room(db, data.room_code, customer_id, data.player_name)


@router.post("/api/games/animal/move", response_model=schemas.GameSessionOut)
def animal_move(
    data: schemas.AnimalMove,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Apply a move, resignation or chat with optimistic version checking."""
    return animal_service.move(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.model_dump(
            exclude={"room_code", "action", "expected_version", "client_action_id"}
        ),
        data.expected_version,
        data.client_action_id,
    )


@router.post(
    "/api/games/chess/create",
    response_model=schemas.GameSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_chess_room(
    data: schemas.ChessRoomCreate,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Create a couple room or an immediate server-AI Chinese-chess game."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return chess_service.create(
        db,
        customer_id,
        data.player_name,
        data.mode,
        data.difficulty,
    )


@router.post("/api/games/chess/join", response_model=schemas.GameSessionOut)
def join_chess_room(
    data: schemas.ChessRoomJoin,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Join the black seat of a private Chinese-chess room."""
    if allow_legacy_customer_header() and not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    return chess_service.join_room(db, data.room_code, customer_id, data.player_name)


@router.post("/api/games/chess/move", response_model=schemas.GameSessionOut)
def chess_move(
    data: schemas.ChessMoveAction,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Apply a versioned move, resignation or chat and persist its replay."""
    return chess_service.move(
        db,
        data.room_code,
        customer_id,
        data.action,
        data.model_dump(
            exclude={"room_code", "action", "expected_version", "client_action_id"}
        ),
        data.expected_version,
        data.client_action_id,
    )


@router.get("/api/games/chess/{room_code}/state", response_model=schemas.GameSessionOut)
def chess_state(
    room_code: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return a member-authorized persisted Chinese-chess board."""
    return chess_service.get_state(db, room_code, customer_id)


@router.get("/api/games/chess/{game_id}/history", response_model=schemas.ChessHistoryOut)
def chess_history(
    game_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return a durable move replay only to an original room member."""
    return chess_service.history(db, game_id, customer_id)


@router.post("/api/games/{game_type}/ai/move", response_model=schemas.GameSessionOut)
def force_game_ai_move(
    game_type: str,
    data: schemas.AIMoveRequest,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Advance an AI only from current server state; arbitrary boards are rejected."""
    if game_type != "chinese_chess":
        raise HTTPException(status_code=409, detail="该游戏会在正常动作接口中自动执行 AI 回合")
    return chess_service.force_ai_move(
        db,
        data.room_code,
        customer_id,
        data.expected_version,
    )


@router.get("/api/games/ai/players", response_model=list[schemas.AIPlayerOut])
def game_ai_players(db: Session = Depends(get_db)):
    """List enabled game AI personas and their transparent difficulty metadata."""
    return game_data_service.ensure_ai_catalog(db)


@router.get("/api/games/ranking", response_model=schemas.GameRankingOut)
def game_ranking(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return private personal totals and a shared-room monthly ranking."""
    return game_data_service.ranking(db, customer_id)


@router.get("/api/games/memories/my", response_model=list[schemas.GameMemoryOut])
def my_game_memories(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return only the current device's game highlights."""
    return game_data_service.list_memories(db, customer_id)


@router.get("/api/games/ai/summary", response_model=schemas.DailyAISummaryOut)
def game_ai_summary(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return the existing explainable rule-based daily companion summary."""
    return game_data_service.daily_summary(db, customer_id)


@router.get("/api/games/{room_code}/state", response_model=schemas.GameSessionOut)
def versioned_game_state(
    room_code: str,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Read viewer-filtered V2.5 state through the stable endpoint."""
    return animal_service.get_any_state(db, room_code, customer_id)


@router.get("/api/games/achievements", response_model=list[schemas.AchievementOut])
def game_achievements(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return persistent achievement progress for the current device."""
    return achievement_service.achievement_catalog(db, customer_id)


@router.get("/api/games/tasks/my", response_model=list[schemas.LoveTaskOut])
def my_game_love_tasks(
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Return post-game couple tasks created by completed landlord rounds."""
    from games.core.service import list_love_tasks

    return list_love_tasks(db, customer_id)


@router.post("/api/games/tasks/{task_id}/complete", response_model=schemas.LoveTaskOut)
def complete_game_love_task(
    task_id: int,
    customer_id: str = Depends(get_customer_id),
    db: Session = Depends(get_db),
):
    """Mark an owned post-game couple promise as completed."""
    from games.core.service import complete_love_task

    return complete_love_task(db, customer_id, task_id)


@router.post("/api/games/dice/rooms", response_model=schemas.DiceRoomOut)
async def create_dice_room(
    data: schemas.DiceRoomCreate,
    db: Session = Depends(get_db),
):
    """Compatibility endpoint for already uploaded 1.x clients."""
    if not allow_legacy_customer_header():
        raise HTTPException(status_code=410, detail="请升级小程序后从统一游戏大厅创建房间")
    if not _legacy_invite_allowed(data.invite_code):
        raise HTTPException(status_code=401, detail="邀请码错误")
    room = game_persistence_service.create_game_room(
        db,
        "dice",
        "legacy_client",
    )
    await game_room_manager.ensure_room(room.room_code, room.game_type, room.max_players)
    return {"room_code": room.room_code}
