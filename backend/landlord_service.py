"""FastAPI-independent orchestration for persisted landlord rooms."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from ai.landlord_ai import LandlordAI
from games.core.engine import GameRuleError
from games.core.player import join, players, require_member
from games.core.room import create_room, require_room
from games.core.service import settle_session_game
from games.core.state import GameSessionStore
from games.landlord.engine import LandlordGame


GAME_TYPE = "landlord"


def _response(room: models.GameRoom, session: models.GameSession, viewer_id: str) -> dict:
    """Shape viewer-filtered state without exposing other players' cards."""
    game = LandlordGame(session.state)
    return {
        "room_id": room.id,
        "room_code": room.room_code,
        "game_type": GAME_TYPE,
        "room_status": room.status,
        "version": session.version,
        "state": game.public_state(viewer_id),
        "updated_at": session.updated_at,
    }


def create(
    db: Session,
    creator_id: str,
    player_name: str,
    difficulty: str,
    mode: str = "couple",
) -> dict:
    """Create a couple table or a solo table with two server AI players."""
    room = create_room(db, GAME_TYPE, creator_id, max_players=1 if mode == "ai" else 2)
    join(db, room.room_code, creator_id)
    game = LandlordGame.waiting(
        [creator_id], {creator_id: player_name}, difficulty, mode
    )
    _run_ai(game)
    session = GameSessionStore(db).create(room, game.serialize())
    db.refresh(room)
    return _response(room, session, creator_id)


def join_room(db: Session, room_code: str, player_id: str, player_name: str) -> dict:
    """Join the second human and let the server deal the complete deck."""
    room = require_room(db, room_code, GAME_TYPE)
    player = join(db, room.room_code, player_id)
    session = GameSessionStore(db).get(room.id)
    state = session.state
    if state.get("mode") == "ai":
        raise HTTPException(status_code=409, detail="人机练习桌不能再加入第二位玩家")
    human_ids = [item.player_id for item in players(db, room.id)]
    names = dict(state.get("names") or {})
    names[player_id] = player_name
    game = LandlordGame.waiting(
        human_ids,
        names,
        state.get("difficulty", "rule"),
        state.get("mode", "couple"),
    )
    if len(human_ids) == 2 and state.get("phase") == "waiting":
        session = GameSessionStore(db).save(session, game.serialize(), session.version)
    db.refresh(room)
    return _response(room, session, player.player_id)


def get_state(db: Session, room_code: str, player_id: str) -> dict:
    """Return the current private view only to a persisted room member."""
    room = require_room(db, room_code, GAME_TYPE)
    require_member(db, room.id, player_id)
    session = GameSessionStore(db).get(room.id)
    return _response(room, session, player_id)


def _run_ai(game: LandlordGame) -> None:
    """Advance consecutive AI turns until a human decision is required."""
    ai = LandlordAI(game.state.get("difficulty", "rule"))
    guard = 0
    while (
        str(game.state.get("turn_id") or "").startswith("ai_")
        and game.state.get("phase") in {"bidding", "playing"}
    ):
        ai_id = game.state["turn_id"]
        decision = ai.choose_action(game.state, ai_id)
        game.apply(ai_id, decision.pop("action"), decision)
        guard += 1
        if guard > 12:
            raise RuntimeError("斗地主 AI 连续行动超过安全上限")


def action(
    db: Session,
    room_code: str,
    player_id: str,
    action_name: str,
    payload: dict,
    expected_version: int,
) -> dict:
    """Validate one human action, run the AI and atomically persist the result."""
    room = require_room(db, room_code, GAME_TYPE)
    require_member(db, room.id, player_id)
    session = GameSessionStore(db).get(room.id)
    game = LandlordGame(session.state)
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
