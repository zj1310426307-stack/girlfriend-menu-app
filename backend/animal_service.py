"""Persistence, membership and AI orchestration for Animal Chess."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from ai.animal_ai import AnimalAI
from games.animal.engine import AI_ID, AnimalGame
from games.core.engine import GameRuleError
from games.core.player import join, require_member
from games.core.room import create_room, require_room
from games.core.service import settle_session_game
from games.core.state import GameSessionStore


GAME_TYPE = "jungle"


def _response(room: models.GameRoom, session: models.GameSession, viewer_id: str) -> dict:
    """Return public board plus the current viewer's color."""
    state = AnimalGame(session.state).public_state(viewer_id)
    state["my_color"] = state.get("colors", {}).get(viewer_id)
    return {
        "room_id": room.id,
        "room_code": room.room_code,
        "game_type": GAME_TYPE,
        "room_status": room.status,
        "version": session.version,
        "state": state,
        "updated_at": session.updated_at,
    }


def create(
    db: Session,
    creator_id: str,
    player_name: str,
    mode: str,
    difficulty: str,
) -> dict:
    """Create a waiting couple room or an immediate human-vs-AI room."""
    room = create_room(db, GAME_TYPE, creator_id, max_players=2)
    join(db, room.room_code, creator_id)
    player_ids = [creator_id]
    names = {creator_id: player_name}
    if mode == "ai":
        player_ids.append(AI_ID)
        names[AI_ID] = "森林 AI"
        room.status = "playing"
        db.commit()
    game = AnimalGame.create(player_ids, names, difficulty)
    game.state["mode"] = mode
    session = GameSessionStore(db).create(room, game.serialize())
    db.refresh(room)
    return _response(room, session, creator_id)


def join_room(db: Session, room_code: str, player_id: str, player_name: str) -> dict:
    """Join the second seat in a couple-mode room and start the board."""
    room = require_room(db, room_code, GAME_TYPE)
    session = GameSessionStore(db).get(room.id)
    if session.state.get("mode") == "ai":
        raise HTTPException(status_code=409, detail="AI 模式不能再加入第二位玩家")
    join(db, room.room_code, player_id)
    game = AnimalGame(session.state)
    try:
        game.add_player(player_id, player_name)
    except GameRuleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session = GameSessionStore(db).save(session, game.serialize(), session.version)
    db.refresh(room)
    return _response(room, session, player_id)


def get_state(db: Session, room_code: str, player_id: str) -> dict:
    """Authorize one human member and return the persisted board."""
    room = require_room(db, room_code, GAME_TYPE)
    require_member(db, room.id, player_id)
    session = GameSessionStore(db).get(room.id)
    return _response(room, session, player_id)


def _run_ai(game: AnimalGame) -> None:
    """Make exactly one legal AI response after a human move."""
    if game.state.get("turn_id") != AI_ID or game.state.get("phase") != "playing":
        return
    ai = AnimalAI(game.state.get("difficulty", "rule"))
    decision = ai.choose_action(game.state, AI_ID)
    game.apply(AI_ID, decision.pop("action"), decision)


def move(
    db: Session,
    room_code: str,
    player_id: str,
    action_name: str,
    payload: dict,
    expected_version: int,
) -> dict:
    """Apply one move/chat/resign, advance AI and compare-and-swap state."""
    room = require_room(db, room_code, GAME_TYPE)
    require_member(db, room.id, player_id)
    session = GameSessionStore(db).get(room.id)
    game = AnimalGame(session.state)
    try:
        game.apply(player_id, action_name, payload)
        _run_ai(game)
    except GameRuleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session = GameSessionStore(db).save(session, game.serialize(), expected_version)
    if game.state.get("phase") == "finished":
        settle_session_game(
            db,
            room,
            game.state,
            game.state.get("winner_id"),
            game.state.get("difficulty", "rule"),
        )
        db.refresh(room)
    return _response(room, session, player_id)


def get_any_state(db: Session, room_code: str, player_id: str) -> dict:
    """Dispatch the shared state endpoint to a V2.5 game implementation."""
    room = crud.get_game_room(db, room_code)
    if room.game_type == "jungle":
        return get_state(db, room_code, player_id)
    if room.game_type == "landlord":
        from landlord_service import get_state as get_landlord_state

        return get_landlord_state(db, room_code, player_id)
    if room.game_type == "chinese_chess":
        from chess_service import get_state as get_chess_state

        return get_chess_state(db, room_code, player_id)
    raise HTTPException(status_code=409, detail="该游戏尚未迁移到统一状态接口")


import crud  # Late import keeps the normal create/join dependency path explicit.
