"""Regression coverage for durable real-time state and private reconnects."""

import asyncio

from fastapi.testclient import TestClient

# Import the shared test app first; it selects and recreates the isolated
# SQLite database before any production modules bind an engine.
from test_api import app

import crud
import models
from database import SessionLocal
from realtime import GameRoomManager, game_room_manager


def _legacy_headers(player_id: str) -> dict:
    return {"X-Customer-Id": player_id}


def _join_message(player_id: str, name: str, game_type: str) -> dict:
    return {
        "type": "join",
        "game": game_type,
        "data": {
            "player_id": player_id,
            "name": name,
            "invite_code": "test-invite",
        },
    }


def test_gomoku_board_recovers_from_postgres_after_manager_restart():
    """A fresh manager must recover the board without memory or Redis."""
    first_id = "gf_durable_gomoku_first"
    second_id = "gf_durable_gomoku_second"

    with TestClient(app):
        with SessionLocal() as db:
            room = crud.create_game_room(db, "gomoku", first_id)
            crud.join_game_room(db, room.room_code, first_id)
            crud.join_game_room(db, room.room_code, second_id)
            room_code = room.room_code
            stored_players = crud.list_game_players(db, room_code)

        async def scenario():
            original = GameRoomManager()
            await original.ensure_room(room_code, "gomoku", 2)
            await original.restore_players(room_code, stored_players)
            assert await original.handle(
                room_code,
                first_id,
                {"type": "move", "game": "gomoku", "data": {"x": 7, "y": 7}},
            ) is None

            # This object has no shared in-process room dictionary. Its only
            # recovery source is the durable GameStateStore boundary.
            restarted = GameRoomManager()
            await restarted.ensure_room(room_code, "gomoku", 2)
            await restarted.restore_players(room_code, stored_players)
            recovered = await restarted.recovery_state(room_code, first_id)
            assert recovered["board"][7][7] == 1
            assert recovered["move_count"] == 1
            assert recovered["turn_id"] == second_id

        asyncio.run(scenario())

        with SessionLocal() as db:
            row = (
                db.query(models.GameState)
                .join(models.GameRoom, models.GameRoom.id == models.GameState.room_id)
                .filter(models.GameRoom.room_code == room_code)
                .one()
            )
            assert row.game_type == "gomoku"
            assert row.state["engine"]["board"][7][7] == 1


def test_dice_reconnect_after_manager_restart_hides_opponent_values():
    """A reconnect may recover the round but reveal only the viewer's dice."""
    first_id = "gf_durable_dice_first"
    second_id = "gf_durable_dice_second"

    with TestClient(app) as client:
        created = client.post(
            "/api/games/rooms",
            headers=_legacy_headers(first_id),
            json={
                "game_type": "dice",
                "creator": first_id,
                "invite_code": "test-invite",
            },
        )
        assert created.status_code == 201
        room_code = created.json()["room_code"]

        with client.websocket_connect(f"/ws/game/{room_code}") as first:
            first.send_json(_join_message(first_id, "我", "dice"))
            assert first.receive_json()["data"]["phase"] == "waiting"
            with client.websocket_connect(f"/ws/game/{room_code}") as second:
                second.send_json(_join_message(second_id, "她", "dice"))
                first.receive_json()
                second.receive_json()

                first.send_json({"type": "roll", "game": "dice", "data": {}})
                first_rolled = first.receive_json()["data"]
                second.receive_json()
                second.send_json({"type": "roll", "game": "dice", "data": {}})
                first_bidding = first.receive_json()["data"]
                second.receive_json()
                assert first_bidding["phase"] == "bidding"
                assert len(first_bidding["my_dice"]) == 5
                assert first_bidding["all_dice"] is None

        issued = client.post(
            "/api/games/reconnect/token",
            headers=_legacy_headers(first_id),
            json={"room_code": room_code},
        )
        assert issued.status_code == 200

        # Remove only the process-local room. The reconnect endpoint must now
        # rebuild it from PostgreSQL and still apply viewer filtering.
        assert room_code in asyncio.run(
            game_room_manager.cleanup_expired([room_code], ttl_seconds=0)
        )
        resumed = client.post(
            "/api/games/reconnect",
            json={"reconnect_token": issued.json()["reconnect_token"]},
        )
        assert resumed.status_code == 200
        state = resumed.json()["state"]
        assert state["phase"] == "bidding"
        assert len(state["my_dice"]) == 5
        assert state["all_dice"] is None
        assert "dice" not in state
        assert all(set(player) <= {"id", "name", "rolled", "rematch_ready", "score"} for player in state["players"])

        with SessionLocal() as db:
            row = (
                db.query(models.GameState)
                .join(models.GameRoom, models.GameRoom.id == models.GameState.room_id)
                .filter(models.GameRoom.room_code == room_code)
                .one()
            )
            # The authoritative snapshot contains both hands; only the API
            # response above is filtered.
            assert set(row.state["dice"]) == {first_id, second_id}
