"""Order and real-time game WebSocket endpoints.

The protocol handlers are moved intact from ``main.py``. Durable room state,
leases, settlement retries and viewer filtering remain in their existing
services so this module only owns transport orchestration.
"""

import asyncio
from datetime import datetime, timezone
import logging
import secrets
import time

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

import couple_profile_service
import crud
import customer_service
import game_recovery_service
import notification_service
from api.dependencies import (
    allow_legacy_customer_header,
    get_admin_invite_code,
    is_admin_token,
)
from core.game_room_lease import acquire_room_lease, release_room_lease
from database import SessionLocal
from game_rewards import settle_game_rewards
from realtime import game_room_manager, order_event_hub


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


def _sync_game_room_status(
    room_code: str,
    room_status: str,
    allow_restart: bool = False,
):
    """Mirror the manager lifecycle into durable room metadata."""
    with SessionLocal() as db:
        room = crud.get_game_room(db, room_code)
        if room.status == "finished" and room_status != "finished" and not allow_restart:
            return
        crud.update_game_room_status(db, room_code, room_status)


def _persist_completed_game(event: dict):
    """Persist one completed real-time round and all existing side effects."""
    with SessionLocal() as db:
        result = dict(event.get("result") or {})
        result["_settlement"] = "pending"
        record = crud.finish_game_room(
            db,
            event["room_code"],
            event.get("winner_id"),
            event.get("duration", 0),
            result,
            event.get("round_number", 1),
        )
        record.settlement_status = "pending"
        record.settlement_attempts = int(record.settlement_attempts or 0) + 1
        record.settlement_error = None
        db.commit()
        settle_game_rewards(
            db,
            record,
            event.get("players") or [],
            event.get("winner_id"),
        )
        replay_state = result.get("final_state") or result
        game_recovery_service.save_replay(db, record, replay_state)
        for player_id in (
            item
            for item in (event.get("players") or [])
            if not str(item).startswith("ai_")
        ):
            couple_profile_service.record_memory_once(
                db,
                player_id,
                "GAME",
                "一起完成了一局游戏",
                f"{event.get('game_type', 'game')} · {event.get('duration', 0)} 秒",
                "GAME_RECORD",
                record.id,
                record.created_at.date(),
            )
            notification_service.create_notification(
                db,
                player_id,
                "GAME_FINISHED",
                "对局结果已经保存",
                "战绩、积分和回放都可以在一起玩中查看。",
                record.id,
            )
        record.result = {**(record.result or {}), "_settlement": "complete"}
        record.settlement_status = "complete"
        record.settlement_error = None
        record.settled_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(record)
        return record


async def _persist_completed_game_with_retry(event: dict):
    """Persist a completed round off the event loop, retrying one transient failure."""
    last_error = None
    for attempt in range(2):
        try:
            return await asyncio.to_thread(_persist_completed_game, event)
        except Exception as error:  # Database drivers expose different transient errors.
            last_error = error
            if attempt == 0:
                await asyncio.sleep(0.2)
    raise last_error


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
    lease_acquired = False
    normalized_room_code = room_code.strip().upper()
    game_type = forced_game_type or "unknown"
    room_session = None
    started_at = time.perf_counter()
    setup_finished_at = started_at
    join_received_at = started_at
    auth_finished_at = started_at
    membership_finished_at = started_at
    try:
        try:
            with SessionLocal() as db:
                room_record = crud.get_game_room_runtime(db, normalized_room_code)
                game_type = room_record.game_type
                is_warm_gomoku_room = (
                    game_type == "gomoku"
                    and await game_room_manager.has_room(normalized_room_code)
                )
                if room_record.status == "finished" and not is_warm_gomoku_room:
                    await _send_game_error(websocket, "房间已经结束", game_type, protocol)
                    await websocket.close(code=4404)
                    return
                if forced_game_type and forced_game_type != game_type:
                    await _send_game_error(
                        websocket,
                        "游戏类型与房间不匹配",
                        game_type,
                        protocol,
                    )
                    await websocket.close(code=4400)
                    return
                lease = acquire_room_lease(db, normalized_room_code)
                if not lease.acquired:
                    await websocket.send_json(
                        {
                            "type": "room_busy",
                            "game": game_type,
                            "room_code": normalized_room_code,
                            "message": "房间正在另一台游戏服务器上运行，正在重新连接",
                            "retry_after_ms": 1200,
                        }
                    )
                    await websocket.close(code=4429)
                    return
                lease_acquired = True
                await game_room_manager.ensure_room(
                    normalized_room_code,
                    room_record.game_type,
                    room_record.max_players,
                )
                await game_room_manager.restore_players(
                    normalized_room_code,
                    crud.list_game_players(db, normalized_room_code),
                )
                setup_finished_at = time.perf_counter()
        except HTTPException as error:
            await _send_game_error(websocket, str(error.detail), game_type, protocol)
            await websocket.close(code=4404)
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
            await _send_game_error(websocket, "请先加入房间", game_type, protocol)
            await websocket.close(code=4400)
            return
        if requested_game != game_type:
            await _send_game_error(websocket, "游戏类型与房间不匹配", game_type, protocol)
            await websocket.close(code=4400)
            return
        customer_token = str(join_data.get("customer_token") or "").strip()
        if customer_token:
            try:
                with SessionLocal() as db:
                    player_id = customer_service.authenticate(
                        db,
                        customer_token,
                        update_last_seen=False,
                    ).id
            except HTTPException:
                await _send_game_error(websocket, "设备登录已失效", game_type, protocol)
                await websocket.close(code=4401)
                return
        elif allow_legacy_customer_header() and secrets.compare_digest(
            str(join_data.get("invite_code") or ""),
            get_admin_invite_code(),
        ):
            logger.warning("deprecated_websocket_player_id game=%s", game_type)
            player_id = str(join_data.get("player_id") or "").strip()[:100]
        else:
            await _send_game_error(websocket, "请重新验证设备后加入房间", game_type, protocol)
            await websocket.close(code=4401)
            return
        auth_finished_at = time.perf_counter()
        player_name = str(join_data.get("name") or "玩家").strip()[:20] or "玩家"
        if not player_id:
            await _send_game_error(websocket, "玩家标识不能为空", game_type, protocol)
            await websocket.close(code=4400)
            return
        try:
            with SessionLocal() as db:
                stored_player = crud.join_game_room(
                    db,
                    normalized_room_code,
                    player_id,
                    commit=False,
                )
                if customer_token:
                    room_session = crud.issue_room_session_token(
                        db,
                        stored_player,
                        commit=False,
                    )
                db.commit()
                stored_players = crud.list_game_players(db, normalized_room_code)
                membership_finished_at = time.perf_counter()
        except HTTPException as error:
            await _send_game_error(websocket, str(error.detail), game_type, protocol)
            await websocket.close(code=4404)
            return
        await game_room_manager.restore_players(normalized_room_code, stored_players)
        joined, message = await game_room_manager.join(
            normalized_room_code,
            player_id,
            player_name,
            websocket,
            protocol=protocol,
            game_type=game_type,
        )
        if not joined:
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
        _sync_game_room_status(
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
            error = await game_room_manager.handle(normalized_room_code, player_id, action)
            if error:
                await _send_game_error(websocket, error, game_type, protocol)
                continue
            _sync_game_room_status(
                normalized_room_code,
                await game_room_manager.room_status(normalized_room_code),
                allow_restart=action_type == "rematch",
            )
            completed_event = await game_room_manager.consume_completed_event(
                normalized_room_code
            )
            if completed_event:
                try:
                    await _persist_completed_game_with_retry(completed_event)
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
        if player_id and joined_room:
            await game_room_manager.leave(normalized_room_code, player_id, websocket)
            try:
                with SessionLocal() as db:
                    crud.mark_game_player_disconnected(
                        db,
                        normalized_room_code,
                        player_id,
                    )
                _sync_game_room_status(
                    normalized_room_code,
                    await game_room_manager.room_status(normalized_room_code),
                )
            except HTTPException:
                pass
        if lease_acquired and not await game_room_manager.has_live_connections(
            normalized_room_code
        ):
            try:
                with SessionLocal() as db:
                    release_room_lease(db, normalized_room_code)
            except Exception:
                logger.exception(
                    "failed to release room lease room=%s",
                    normalized_room_code,
                )


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
