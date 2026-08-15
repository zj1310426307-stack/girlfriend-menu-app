"""Order and real-time game WebSocket endpoints.

The protocol handlers are moved intact from ``main.py``. Durable room state,
leases, settlement retries and viewer filtering remain in their existing
services so this module only owns transport orchestration.
"""

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.dependencies import (
    allow_legacy_customer_header,
    get_admin_invite_code,
    is_admin_token,
)
from core.telemetry import set_span_attribute, trace_span
from game_runtime import game_room_manager
from realtime_events import order_event_hub
from services import game_settlement_service, game_socket_session_service


# Temporary compatibility aliases keep maintenance scripts and direct tests
# stable while callers migrate to the extracted settlement service.
_persist_completed_game = game_settlement_service.persist_completed_game
_persist_completed_game_with_retry = (
    game_settlement_service.persist_completed_game_with_retry
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/admin/orders")
async def admin_order_events(websocket: WebSocket):
    """Authenticate and stream order events with the original ping/pong protocol."""
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=8)
        if auth_message.get("type") != "auth" or not is_admin_token(
            auth_message.get("token")
        ):
            await websocket.send_json({"type": "error", "message": "管理登录已失效"})
            await websocket.close(code=4401)
            return
        await order_event_hub.add(websocket)
        await websocket.send_json({"type": "ready"})
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await order_event_hub.remove(websocket)


async def _send_game_error(
    websocket: WebSocket,
    message: str,
    game_type: str,
    protocol: str,
):
    """Shape an error for either the legacy dice or unified game protocol."""
    if protocol == "legacy":
        await websocket.send_json({"type": "error", "message": message})
    else:
        await websocket.send_json({"type": "error", "game": game_type, "message": message})


async def _game_room_socket(
    websocket: WebSocket,
    room_code: str,
    protocol: str,
    forced_game_type: str | None = None,
):
    """Run the unchanged lease, join, action, settlement and disconnect lifecycle."""
    await websocket.accept()
    player_id = None
    joined_room = False
    normalized_room_code = room_code.strip().upper()
    game_type = forced_game_type or "unknown"
    room_session = None
    setup = None
    started_at = time.perf_counter()
    setup_finished_at = started_at
    join_received_at = started_at
    auth_finished_at = started_at
    membership_finished_at = started_at
    try:
        with trace_span(
            "game.websocket.join",
            {"game.type": game_type, "result": "error"},
        ) as join_span:
            try:
                setup = await game_socket_session_service.load_room_and_acquire_lease(
                    normalized_room_code,
                    forced_game_type,
                )
                game_type = setup.game_type
                set_span_attribute(join_span, "game.type", game_type)
                await game_socket_session_service.restore_room_runtime(setup)
                setup_finished_at = time.perf_counter()
            except game_socket_session_service.SocketSessionError as error:
                game_type = error.game_type or game_type
                set_span_attribute(join_span, "game.type", game_type)
                set_span_attribute(
                    join_span,
                    "result",
                    "busy" if error.close_code == 4429 else "rejected",
                )
                if error.close_code == 4429:
                    await websocket.send_json(
                        {
                            "type": "room_busy",
                            "game": game_type,
                            "room_code": normalized_room_code,
                            "message": "房间正在另一台游戏服务器上运行，正在重新连接",
                            "retry_after_ms": 1200,
                        }
                    )
                else:
                    await _send_game_error(websocket, error.message, game_type, protocol)
                await websocket.close(code=error.close_code)
                return

            join_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            join_received_at = time.perf_counter()
            join_data = (
                join_message.get("data")
                if isinstance(join_message.get("data"), dict)
                else join_message
            )
            requested_game = str(
                join_message.get("game") or forced_game_type or game_type
            ).lower()
            if str(join_message.get("type") or "").lower() != "join":
                set_span_attribute(join_span, "result", "rejected")
                await _send_game_error(websocket, "请先加入房间", game_type, protocol)
                await websocket.close(code=4400)
                return
            if requested_game != game_type:
                set_span_attribute(join_span, "result", "rejected")
                await _send_game_error(websocket, "游戏类型与房间不匹配", game_type, protocol)
                await websocket.close(code=4400)
                return
            try:
                allow_legacy = allow_legacy_customer_header()
                authenticated_player = game_socket_session_service.authenticate_player(
                    join_data,
                    allow_legacy_identity=allow_legacy,
                    legacy_invite_code=get_admin_invite_code() if allow_legacy else "",
                    game_type=game_type,
                )
                player_id = authenticated_player.player_id
            except game_socket_session_service.SocketSessionError as error:
                set_span_attribute(
                    join_span,
                    "result",
                    "unauthorized" if error.close_code == 4401 else "rejected",
                )
                await _send_game_error(websocket, error.message, game_type, protocol)
                await websocket.close(code=error.close_code)
                return
            auth_finished_at = time.perf_counter()
            try:
                membership = game_socket_session_service.persist_membership(
                    setup,
                    authenticated_player,
                )
                room_session = membership.room_session
                membership_finished_at = time.perf_counter()
            except game_socket_session_service.SocketSessionError as error:
                set_span_attribute(join_span, "result", "rejected")
                await _send_game_error(websocket, error.message, game_type, protocol)
                await websocket.close(code=error.close_code)
                return
            joined, message = await game_socket_session_service.join_runtime(
                setup,
                authenticated_player,
                websocket,
                protocol,
                membership.players,
            )
            if not joined:
                set_span_attribute(join_span, "result", "rejected")
                await _send_game_error(websocket, message, game_type, protocol)
                await websocket.close(code=4404)
                return
            joined_room = True
            first_state_finished_at = time.perf_counter()
            logger.info(
                "game_ws_first_state room=%s game=%s setup_ms=%d client_join_wait_ms=%d "
                "auth_ms=%d membership_ms=%d manager_join_ms=%d total_ms=%d",
                normalized_room_code,
                game_type,
                round((setup_finished_at - started_at) * 1000),
                round((join_received_at - setup_finished_at) * 1000),
                round((auth_finished_at - join_received_at) * 1000),
                round((membership_finished_at - auth_finished_at) * 1000),
                round((first_state_finished_at - membership_finished_at) * 1000),
                round((first_state_finished_at - started_at) * 1000),
            )
            set_span_attribute(join_span, "result", "success")
        if room_session:
            await websocket.send_json(
                {
                    "type": "session",
                    "game": game_type,
                    "room_code": normalized_room_code,
                    "data": {
                        "room_session_token": room_session[0],
                        "expires_at": room_session[1].isoformat(),
                    },
                }
            )
        game_socket_session_service.sync_room_status(
            normalized_room_code,
            await game_room_manager.room_status(normalized_room_code),
        )
        while True:
            action = await websocket.receive_json()
            action_type = str(action.get("type") or "").lower()
            if action_type == "ping":
                pong = {"type": "pong"}
                if protocol != "legacy":
                    pong.update(game=game_type, data={})
                await websocket.send_json(pong)
                continue
            previous_room_status = await game_room_manager.room_status(
                normalized_room_code
            )
            error = await game_room_manager.handle(normalized_room_code, player_id, action)
            if error:
                await _send_game_error(websocket, error, game_type, protocol)
                continue
            current_room_status = await game_room_manager.room_status(
                normalized_room_code
            )
            if current_room_status != previous_room_status or action_type == "rematch":
                game_socket_session_service.sync_room_status(
                    normalized_room_code,
                    current_room_status,
                    allow_restart=action_type == "rematch",
                )
            completed_event = await game_room_manager.consume_completed_event(
                normalized_room_code
            )
            if completed_event:
                try:
                    await game_settlement_service.persist_completed_game_with_retry(
                        completed_event
                    )
                    await game_room_manager.acknowledge_completed_event(
                        normalized_room_code
                    )
                except Exception:
                    await game_room_manager.restore_completed_event(
                        normalized_room_code,
                        completed_event,
                    )
                    logger.exception(
                        "Failed to persist completed %s round in room %s",
                        game_type,
                        normalized_room_code,
                    )
                    await _send_game_error(
                        websocket,
                        "对局已经结束，但成长记录暂时保存失败",
                        game_type,
                        protocol,
                    )
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if setup and player_id and joined_room:
            await game_socket_session_service.disconnect_player(
                setup,
                player_id,
                websocket,
            )
        if setup:
            await game_socket_session_service.release_lease_if_idle(setup)


@router.websocket("/ws/game/{room_code}")
async def unified_game_room_socket(websocket: WebSocket, room_code: str):
    """Serve the unified V2 real-time game protocol."""
    await _game_room_socket(websocket, room_code, protocol="v2")


@router.websocket("/ws/games/dice/{room_code}")
async def dice_room_socket(websocket: WebSocket, room_code: str):
    """Serve the legacy dice WebSocket protocol without changing its payloads."""
    await _game_room_socket(
        websocket,
        room_code,
        protocol="legacy",
        forced_game_type="dice",
    )
