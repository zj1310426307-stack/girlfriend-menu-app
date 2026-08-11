"""Regression coverage for long-running game runtime guarantees."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from test_api import app

import crud
import game_maintenance
import models
from core.game_room_lease import acquire_room_lease
from database import SessionLocal
from games.animal.engine import AnimalGame, _position_hash
from games.chess.board import board_hash
from games.chess.engine import ChessGame


def _headers(player_id: str) -> dict:
    return {"X-Customer-Id": player_id}


def test_database_room_lease_prevents_split_brain_and_allows_takeover():
    """Only one instance owns a room until its persisted lease expires."""
    with TestClient(app):
        with SessionLocal() as db:
            room = crud.create_game_room(db, "gomoku", "gf_lease_owner")
            first = acquire_room_lease(db, room.room_code, "instance-a", 30)
            assert first.acquired is True
            blocked = acquire_room_lease(db, room.room_code, "instance-b", 30)
            assert blocked.acquired is False
            room = crud.get_game_room(db, room.room_code)
            room.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
            takeover = acquire_room_lease(db, room.room_code, "instance-b", 30)
            assert takeover.acquired is True
            assert takeover.owner_instance_id == "instance-b"
            assert takeover.lease_epoch > first.lease_epoch


def test_stale_room_is_archived_not_deleted():
    """Cleanup removes ghost rooms from active lists while preserving the row."""
    with TestClient(app):
        with SessionLocal() as db:
            room = crud.create_game_room(db, "jungle", "gf_stale_room")
            room.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
            assert room.room_code in crud.expire_stale_game_rooms(db)
            archived = crud.get_game_room(db, room.room_code)
            assert archived.status == "abandoned"
            assert archived.abandoned_at is not None
            assert archived.expires_at is None


def test_animal_action_id_replays_exactly_once_and_rejects_conflict():
    """A timed-out HTTP response can be resent without moving a second time."""
    player = "gf_idempotent_animal"
    action_id = "animal_retry_0001"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/animal/create",
            headers=_headers(player),
            json={
                "player_name": "我",
                "mode": "ai",
                "difficulty": "rule",
                "invite_code": "test-invite",
            },
        ).json()
        request = {
            "room_code": created["room_code"],
            "action": "MOVE",
            "piece_id": "blue_lion",
            "x": 0,
            "y": 1,
            "expected_version": created["version"],
            "client_action_id": action_id,
        }
        first = client.post(
            "/api/games/animal/move",
            headers=_headers(player),
            json=request,
        )
        repeated = client.post(
            "/api/games/animal/move",
            headers=_headers(player),
            json=request,
        )
        assert first.status_code == repeated.status_code == 200
        assert repeated.json()["version"] == first.json()["version"]
        assert repeated.json()["state"] == first.json()["state"]
        conflicting = client.post(
            "/api/games/animal/move",
            headers=_headers(player),
            json={**request, "x": 1},
        )
        assert conflicting.status_code == 409
        with SessionLocal() as db:
            room = crud.get_game_room(db, created["room_code"])
            assert db.query(models.GameAction).filter(
                models.GameAction.room_id == room.id,
                models.GameAction.client_action_id == action_id,
            ).count() == 1


def test_pending_settlement_is_repaired_without_duplicate_rewards():
    """A process crash after final state persistence is repaired idempotently."""
    player = "gf_settlement_repair"
    with TestClient(app) as client:
        created = client.post(
            "/api/games/animal/create",
            headers=_headers(player),
            json={
                "player_name": "我",
                "mode": "ai",
                "difficulty": "rule",
                "invite_code": "test-invite",
            },
        ).json()
        with SessionLocal() as db:
            room = crud.get_game_room(db, created["room_code"])
            session = db.query(models.GameSession).filter(
                models.GameSession.room_id == room.id
            ).one()
            state = deepcopy(session.state)
            state.update(
                phase="finished",
                winner_id=player,
                turn_id=None,
                result_reason="test_crash_recovery",
            )
            session.state = state
            db.commit()
            record = crud.finish_game_room(
                db,
                room.room_code,
                player,
                12,
                {"_settlement": "pending", "state": state},
                1,
            )
            record_id = record.id
            result = game_maintenance.reconcile_game_settlements(db)
            assert result["repaired"] >= 1
            repaired = db.get(models.GameRecord, record_id)
            assert repaired.settlement_status == "complete"
            first_count = db.query(models.LoveScore).filter(
                models.LoveScore.customer_id == player,
                models.LoveScore.related_id == record_id,
            ).count()
            game_maintenance.reconcile_game_settlements(db)
            second_count = db.query(models.LoveScore).filter(
                models.LoveScore.customer_id == player,
                models.LoveScore.related_id == record_id,
            ).count()
            assert first_count == second_count


def test_animal_and_chess_timeout_and_threefold_draw_rules():
    """Both board games terminate stalled and repeated positions deterministically."""
    animal_timeout = AnimalGame.create(["boy", "girl"])
    animal_timeout.state["turn_deadline_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    assert animal_timeout.expire_turn() is True
    assert animal_timeout.state["winner_id"] == "girl"
    assert animal_timeout.state["result_reason"] == "turn_timeout"

    animal_draw = AnimalGame.create(["boy", "girl"])
    next_pieces = deepcopy(animal_draw.state["pieces"])
    lion = next(piece for piece in next_pieces if piece["id"] == "blue_lion")
    lion.update(x=0, y=1)
    repeated = _position_hash(next_pieces, "red")
    animal_draw.state["position_history"] = [repeated, repeated]
    animal_draw.move("boy", "blue_lion", 0, 1)
    assert animal_draw.state["winner_id"] is None
    assert animal_draw.state["draw_reason"] == "threefold_repetition"

    chess_timeout = ChessGame.create(["red", "black"])
    chess_timeout.state["turn_deadline_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    assert chess_timeout.expire_turn() is True
    assert chess_timeout.state["winner_id"] == "black"

    chess_draw = ChessGame.create(["red", "black"])
    next_pieces = deepcopy(chess_draw.state["pieces"])
    pawn = next(piece for piece in next_pieces if piece["id"] == "red_pawn_0")
    pawn.update(y=5)
    repeated = board_hash(next_pieces, "black")
    chess_draw.state["position_history"] = [repeated, repeated]
    chess_draw.move("red", "red_pawn_0", 0, 5)
    assert chess_draw.state["winner_id"] is None
    assert chess_draw.state["draw_reason"] == "threefold_repetition"
