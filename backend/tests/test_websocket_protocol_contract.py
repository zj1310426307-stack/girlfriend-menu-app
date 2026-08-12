"""Golden-field tests for the deployed WebSocket protocol boundary."""

import asyncio
import uuid

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core import game_room_lease
from core.rate_limit import MemoryRateLimiter
from database import SessionLocal
from realtime import game_room_manager
from services import game_persistence_service
from test_api import app, admin_token


def _legacy_join(player_id: str) -> dict:
    """Build the deployed legacy join frame without optional fields."""
    return {
        "type": "join",
        "player_id": player_id,
        "name": "测试玩家",
        "invite_code": "test-invite",
    }


def _create_room(game_type: str = "dice") -> str:
    """Create a durable room directly so tests isolate the socket contract."""
    with SessionLocal() as db:
        room = game_persistence_service.create_game_room(
            db,
            game_type,
            f"gf_contract_{uuid.uuid4().hex[:8]}",
        )
        return room.room_code


def test_admin_ready_ping_pong_and_invalid_auth_close_code():
    """Freeze admin ready/pong fields and its authentication close code."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/admin/orders") as socket:
            socket.send_json({"type": "auth", "token": admin_token(client)})
            assert socket.receive_json() == {"type": "ready"}
            socket.send_json({"type": "ping"})
            assert socket.receive_json() == {"type": "pong"}

        try:
            with client.websocket_connect("/ws/admin/orders") as socket:
                socket.send_json({"type": "auth", "token": "invalid"})
                assert socket.receive_json() == {
                    "type": "error",
                    "message": "管理登录已失效",
                }
                socket.receive_json()
        except WebSocketDisconnect as error:
            assert error.code == 4401


def test_unified_join_first_error_and_v2_pong_shape():
    """Freeze the unified error envelope, join-first close and pong fields."""
    room_code = _create_room("dice")
    with TestClient(app) as client:
        try:
            with client.websocket_connect(f"/ws/game/{room_code}") as socket:
                socket.send_json({"type": "ping", "game": "dice", "data": {}})
                assert socket.receive_json() == {
                    "type": "error",
                    "game": "dice",
                    "message": "请先加入房间",
                }
                socket.receive_json()
        except WebSocketDisconnect as error:
            assert error.code == 4400

    room_code = _create_room("dice")
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/game/{room_code}") as socket:
            socket.send_json(
                {
                    "type": "join",
                    "game": "dice",
                    "data": _legacy_join("gf_v2_pong"),
                }
            )
            assert socket.receive_json()["type"] == "state"
            socket.send_json({"type": "ping", "game": "dice", "data": {}})
            assert socket.receive_json() == {
                "type": "pong",
                "game": "dice",
                "data": {},
            }


def test_missing_room_uses_v2_error_envelope_and_close_4404():
    """Freeze the missing-room lifecycle close separately from join errors."""
    with TestClient(app) as client:
        try:
            with client.websocket_connect("/ws/game/NOEXST") as socket:
                payload = socket.receive_json()
                assert payload["type"] == "error"
                assert payload["game"] == "unknown"
                assert "房间不存在" in payload["message"]
                socket.receive_json()
        except WebSocketDisconnect as error:
            assert error.code == 4404


def test_legacy_error_shape_and_invalid_identity_close_code():
    """Freeze legacy error privacy and customer authentication close 4401."""
    room_code = _create_room("dice")
    with TestClient(app) as client:
        try:
            with client.websocket_connect(f"/ws/games/dice/{room_code}") as socket:
                socket.send_json({"type": "ping"})
                assert socket.receive_json() == {
                    "type": "error",
                    "message": "请先加入房间",
                }
                socket.receive_json()
        except WebSocketDisconnect as error:
            assert error.code == 4400

    room_code = _create_room("dice")
    with TestClient(app) as client:
        try:
            with client.websocket_connect(f"/ws/game/{room_code}") as socket:
                socket.send_json(
                    {
                        "type": "join",
                        "game": "dice",
                        "data": {"customer_token": "invalid", "name": "测试"},
                    }
                )
                assert socket.receive_json() == {
                    "type": "error",
                    "game": "dice",
                    "message": "设备登录已失效",
                }
                socket.receive_json()
        except WebSocketDisconnect as error:
            assert error.code == 4401


def test_customer_session_payload_fields_are_stable():
    """Freeze the one-time room session credential envelope after first state."""
    with TestClient(app) as client:
        session = client.post(
            "/api/customers/session",
            json={"invite_code": "test-invite", "display_name": "测试"},
        ).json()
        created = client.post(
            "/api/games/rooms",
            headers={"Authorization": f"Bearer {session['customer_token']}"},
            json={
                "game_type": "dice",
                "creator": session["customer_id"],
                "invite_code": "test-invite",
            },
        )
        room_code = created.json()["room_code"]
        with client.websocket_connect(f"/ws/game/{room_code}") as socket:
            socket.send_json(
                {
                    "type": "join",
                    "game": "dice",
                    "data": {
                        "customer_token": session["customer_token"],
                        "name": "测试",
                    },
                }
            )
            assert socket.receive_json()["type"] == "state"
            payload = socket.receive_json()
            assert set(payload) == {"type", "game", "room_code", "data"}
            assert payload["type"] == "session"
            assert payload["game"] == "dice"
            assert payload["room_code"] == room_code
            assert set(payload["data"]) == {"room_session_token", "expires_at"}
            assert payload["data"]["room_session_token"].startswith("gfr_")


def test_same_player_can_reconnect_while_opponent_stays_online(monkeypatch):
    """Protect the production reconnect race while another socket owns a seat."""
    import api.dependencies as api_dependencies

    monkeypatch.setattr(api_dependencies, "rate_limiter", MemoryRateLimiter())
    with TestClient(app) as client:
        sessions = [
            client.post(
                "/api/customers/session",
                json={
                    "invite_code": "test-invite",
                    "display_name": f"reconnect-{suffix}",
                    "device_label": f"contract-{uuid.uuid4().hex}",
                },
            ).json()
            for suffix in ("a", "b")
        ]
        created = client.post(
            "/api/games/rooms",
            headers={"Authorization": f"Bearer {sessions[0]['customer_token']}"},
            json={
                "game_type": "gomoku",
                "creator": sessions[0]["customer_id"],
                "invite_code": "test-invite",
            },
        )
        room_code = created.json()["room_code"]

        first_context = client.websocket_connect(f"/ws/game/{room_code}")
        first = first_context.__enter__()
        try:
            first.send_json(
                {
                    "type": "join",
                    "game": "gomoku",
                    "data": {
                        "customer_token": sessions[0]["customer_token"],
                        "name": "reconnect-a",
                    },
                }
            )
            assert first.receive_json()["type"] == "state"
            assert first.receive_json()["type"] == "session"

            with client.websocket_connect(f"/ws/game/{room_code}") as second:
                second.send_json(
                    {
                        "type": "join",
                        "game": "gomoku",
                        "data": {
                            "customer_token": sessions[1]["customer_token"],
                            "name": "reconnect-b",
                        },
                    }
                )
                assert second.receive_json()["type"] == "state"
                assert second.receive_json()["type"] == "session"
                assert first.receive_json()["type"] == "state"
                first.close()

                with client.websocket_connect(f"/ws/game/{room_code}") as reconnected:
                    reconnected.send_json(
                        {
                            "type": "join",
                            "game": "gomoku",
                            "data": {
                                "customer_token": sessions[0]["customer_token"],
                                "name": "reconnect-a",
                            },
                        }
                    )
                    state = reconnected.receive_json()
                    assert state["type"] == "state"
                    assert state["data"]["phase"] == "playing"
                    assert reconnected.receive_json()["type"] == "session"
        finally:
            try:
                first.close()
            finally:
                first_context.__exit__(None, None, None)


def test_non_owner_gets_exact_room_busy_payload_and_close_code(monkeypatch):
    """Freeze split-brain retry payload fields and close code 4429."""
    room_code = _create_room("dice")
    with SessionLocal() as db:
        owned = game_room_lease.acquire_room_lease(
            db,
            room_code,
            owner_instance_id="other-instance",
            lease_seconds=60,
        )
        assert owned.acquired
    monkeypatch.setattr(game_room_lease, "INSTANCE_ID", "this-instance")
    import services.game_socket_session_service as socket_service

    monkeypatch.setattr(socket_service, "acquire_room_lease", game_room_lease.acquire_room_lease)
    with TestClient(app) as client:
        try:
            with client.websocket_connect(f"/ws/game/{room_code}") as socket:
                assert socket.receive_json() == {
                    "type": "room_busy",
                    "game": "dice",
                    "room_code": room_code,
                    "message": "房间正在另一台游戏服务器上运行，正在重新连接",
                    "retry_after_ms": 1200,
                }
                socket.receive_json()
        except WebSocketDisconnect as error:
            assert error.code == 4429
    with SessionLocal() as db:
        game_room_lease.release_room_lease(
            db,
            room_code,
            owner_instance_id="other-instance",
        )
    asyncio.run(game_room_manager.cleanup_expired([room_code], ttl_seconds=0))
