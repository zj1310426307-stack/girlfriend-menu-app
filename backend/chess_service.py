"""Persistence, membership, AI and replay orchestration for Chinese chess."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from ai.chess_ai import ChessAI
from game_data_service import add_memory, rebuild_statistics
from games.chess.engine import AI_ID, ChessGame
from games.chess.move import format_position, parse_position
from games.core.engine import GameRuleError
from games.core.player import join, require_member
from games.core.room import create_room, require_room
from games.core.service import settle_session_game
from games.core.state import GameSessionStore


GAME_TYPE = "chinese_chess"


def _response(room: models.GameRoom, session: models.GameSession, viewer_id: str) -> dict:
    """Shape one viewer-authorized response from the authoritative session."""
    state = ChessGame(session.state).public_state(viewer_id)
    return {"room_id": room.id, "room_code": room.room_code, "game_type": GAME_TYPE, "room_status": room.status, "version": session.version, "state": state, "updated_at": session.updated_at}


def _header(db: Session, room_id: int, round_number: int = 1) -> models.ChessGame:
    """Load the durable replay header for a room round."""
    header = db.query(models.ChessGame).filter(models.ChessGame.room_id == room_id, models.ChessGame.round_number == round_number).first()
    if not header:
        raise HTTPException(status_code=404, detail="象棋棋谱尚未建立")
    return header


def create(db: Session, creator_id: str, player_name: str, mode: str, difficulty: str) -> dict:
    """Create a waiting couple room or immediate human-vs-AI training game."""
    room = create_room(db, GAME_TYPE, creator_id, max_players=2)
    join(db, room.room_code, creator_id)
    player_ids = [creator_id]
    names = {creator_id: player_name}
    black_player = None
    if mode == "ai":
        player_ids.append(AI_ID)
        names[AI_ID] = "象棋陪练官"
        black_player = AI_ID
        room.status = "playing"
    header = models.ChessGame(room_id=room.id, red_player=creator_id, black_player=black_player)
    db.add(header)
    db.commit()
    db.refresh(header)
    game = ChessGame.create(player_ids, names, difficulty)
    game.state["mode"] = mode
    game.state["chess_game_id"] = header.id
    session = GameSessionStore(db).create(room, game.serialize())
    db.refresh(room)
    return _response(room, session, creator_id)


def join_room(db: Session, room_code: str, player_id: str, player_name: str) -> dict:
    """Join the black seat and start a couple match without resetting the board."""
    room = require_room(db, room_code, GAME_TYPE)
    session = GameSessionStore(db).get(room.id)
    if session.state.get("mode") == "ai":
        raise HTTPException(status_code=409, detail="AI 训练房不能再加入第二位玩家")
    join(db, room.room_code, player_id)
    game = ChessGame(session.state)
    try:
        game.add_player(player_id, player_name)
    except GameRuleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    header = _header(db, room.id)
    header.black_player = player_id
    db.commit()
    session = GameSessionStore(db).save(session, game.serialize(), session.version)
    db.refresh(room)
    return _response(room, session, player_id)


def get_state(db: Session, room_code: str, player_id: str) -> dict:
    """Authorize room membership before revealing the public board."""
    room = require_room(db, room_code, GAME_TYPE)
    require_member(db, room.id, player_id)
    store = GameSessionStore(db)
    session = store.get(room.id)
    game = ChessGame(session.state)
    if game.expire_turn():
        session = store.save(session, game.serialize(), session.version)
        _persist_moves(db, room, game.state)
        _finish(db, room, game.state)
        db.refresh(room)
    return _response(room, session, player_id)


def _run_ai(game: ChessGame) -> None:
    """Apply exactly one server-generated AI move when the AI owns the turn."""
    if game.state.get("turn_id") != AI_ID or game.state.get("phase") != "playing":
        return
    decision = ChessAI(game.state.get("difficulty", "rule")).choose_action(game.state, AI_ID)
    game.apply(AI_ID, decision.pop("action"), decision)


def _persist_moves(db: Session, room: models.GameRoom, state: dict) -> None:
    """Append all newly observed state-history entries to the immutable chess log."""
    header = _header(db, room.id, int(state.get("round", 1)))
    existing = {number for (number,) in db.query(models.ChessMove.move_number).filter(models.ChessMove.game_id == header.id)}
    for entry in state.get("move_history", []):
        number = int(entry["number"])
        if number in existing:
            continue
        db.add(models.ChessMove(
            game_id=header.id,
            move_number=number,
            player=entry["player_id"],
            piece=entry["piece"],
            from_pos=format_position(entry["from"]["x"], entry["from"]["y"]),
            to_pos=format_position(entry["to"]["x"], entry["to"]["y"]),
            notation=entry.get("notation", ""),
        ))
    header.move_count = int(state.get("move_count", 0))
    db.commit()


def _finish(db: Session, room: models.GameRoom, state: dict) -> None:
    """Run shared rewards once, finalize replay data, statistics and memories."""
    record = settle_session_game(db, room, state, state.get("winner_id"), state.get("difficulty", "rule"))
    header = _header(db, room.id, int(state.get("round", 1)))
    header.winner = state.get("winner_id")
    header.move_count = int(state.get("move_count", 0))
    header.duration = record.duration
    header.finished_at = datetime.now()
    db.commit()
    human_ids = [player.player_id for player in room.players]
    for player_id in human_ids:
        add_memory(db, player_id, GAME_TYPE, "FIRST_CHESS", "我们完成了第一局中国象棋。", 0)
        result_text = "赢下" if state.get("winner_id") == player_id else "完成"
        add_memory(db, player_id, GAME_TYPE, "CHESS_RESULT", f"{result_text}一局中国象棋，共走了 {header.move_count} 步。", record.id)
    rebuild_statistics(db)


def move(
    db: Session,
    room_code: str,
    player_id: str,
    action_name: str,
    payload: dict,
    expected_version: int,
    client_action_id: str | None = None,
) -> dict:
    """Apply a versioned move/resign/chat, then persist AI response and replay."""
    room = require_room(db, room_code, GAME_TYPE)
    require_member(db, room.id, player_id)
    store = GameSessionStore(db)
    session = store.get(room.id)
    replayed = store.replay_action(
        room,
        player_id,
        client_action_id,
        action_name,
        payload,
        expected_version,
    )
    if replayed:
        return _response(room, replayed, player_id)
    game = ChessGame(session.state)
    if game.expire_turn():
        expired = store.save(session, game.serialize(), session.version)
        _persist_moves(db, room, game.state)
        _finish(db, room, game.state)
        db.refresh(room)
        return _response(room, expired, player_id)
    data = dict(payload)
    if action_name == "MOVE":
        try:
            x1, y1 = parse_position(str(data.get("from_pos") or ""))
            x2, y2 = parse_position(str(data.get("to_pos") or ""))
        except GameRuleError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        source = next((piece for piece in game.state.get("pieces", []) if piece["alive"] and piece["x"] == x1 and piece["y"] == y1), None)
        data = {"piece_id": source["id"] if source else "", "x": x2, "y": y2}
    try:
        game.apply(player_id, action_name, data)
        _run_ai(game)
    except GameRuleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    committed = store.save_action(
        session,
        room,
        player_id,
        client_action_id,
        action_name,
        payload,
        game.serialize(),
        expected_version,
    )
    if not committed.replayed:
        _persist_moves(db, room, game.state)
    if game.state.get("phase") == "finished":
        _finish(db, room, game.state)
        db.refresh(room)
    return _response(room, committed, player_id)


def force_ai_move(db: Session, room_code: str, player_id: str, expected_version: int) -> dict:
    """Advance an AI turn only from its current persisted server state."""
    room = require_room(db, room_code, GAME_TYPE)
    require_member(db, room.id, player_id)
    session = GameSessionStore(db).get(room.id)
    game = ChessGame(session.state)
    if game.state.get("turn_id") != AI_ID:
        raise HTTPException(status_code=409, detail="当前不是 AI 回合")
    try:
        _run_ai(game)
    except GameRuleError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    session = GameSessionStore(db).save(session, game.serialize(), expected_version)
    _persist_moves(db, room, game.state)
    if game.state.get("phase") == "finished":
        _finish(db, room, game.state)
        db.refresh(room)
    return _response(room, session, player_id)


def history(db: Session, game_id: int, player_id: str) -> dict:
    """Return a replay only to a human who occupied the original room."""
    game = db.query(models.ChessGame).filter(models.ChessGame.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="象棋棋谱不存在")
    require_member(db, game.room_id, player_id)
    return {"game": game, "moves": game.moves}
