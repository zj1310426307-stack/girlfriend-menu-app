"""Session orchestration shared by legacy and unified game WebSockets.

This service owns durable room/session work and process-local runtime setup.
Protocol parsing, public payload shapes, close codes and socket receive/send
operations intentionally remain in the API router.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import secrets

from fastapi import HTTPException

import customer_service
from core.game_room_lease import acquire_room_lease, release_room_lease
from database import SessionLocal
from game_runtime import game_room_manager
from services import game_persistence_service


logger = logging.getLogger(__name__)


class SocketSessionError(Exception):
    """Describe a session failure while leaving its wire representation to API code."""

    def __init__(
        self,
        message: str,
        close_code: int,
        game_type: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.close_code = close_code
        self.game_type = game_type


@dataclass(frozen=True)
class RoomSetup:
    """Room metadata returned after the PostgreSQL lease is acquired."""

    room_code: str
    game_type: str
    max_players: int
    lease_acquired: bool


@dataclass(frozen=True)
class AuthenticatedPlayer:
    """Server-owned player identity resolved from one join request."""

    player_id: str
    player_name: str
    customer_token: str


@dataclass(frozen=True)
class Membership:
    """Durable seats and optional one-time room session credential."""

    players: list
    room_session: tuple[str, object] | None


async def load_room_and_acquire_lease(
    room_code: str,
    forced_game_type: str | None = None,
) -> RoomSetup:
    """Validate room lifecycle/type and acquire its single-writer lease."""
    normalized = room_code.strip().upper()
    with SessionLocal() as db:
        try:
            room = game_persistence_service.get_game_room_runtime(db, normalized)
        except HTTPException as error:
            raise SocketSessionError(
                str(error.detail),
                4404,
                forced_game_type,
            ) from error

        is_warm_gomoku_room = (
            room.game_type == "gomoku"
            and await game_room_manager.has_room(normalized)
        )
        if room.status == "finished" and not is_warm_gomoku_room:
            raise SocketSessionError("房间已经结束", 4404, room.game_type)
        if forced_game_type and forced_game_type != room.game_type:
            raise SocketSessionError(
                "游戏类型与房间不匹配",
                4400,
                room.game_type,
            )
        lease = acquire_room_lease(db, normalized)
        if not lease.acquired:
            raise SocketSessionError("room_busy", 4429, room.game_type)
        return RoomSetup(normalized, room.game_type, room.max_players, True)


async def restore_room_runtime(setup: RoomSetup) -> None:
    """Restore snapshot container and durable seats into the live manager."""
    try:
        await game_room_manager.ensure_room(
            setup.room_code,
            setup.game_type,
            setup.max_players,
        )
        with SessionLocal() as db:
            players = game_persistence_service.list_game_players(db, setup.room_code)
        await game_room_manager.restore_players(setup.room_code, players)
    except HTTPException as error:
        raise SocketSessionError(
            str(error.detail),
            4404,
            setup.game_type,
        ) from error


def authenticate_player(
    join_data: dict,
    *,
    allow_legacy_identity: bool,
    legacy_invite_code: str,
    game_type: str,
) -> AuthenticatedPlayer:
    """Resolve a customer token or the explicitly enabled legacy test bridge."""
    customer_token = str(join_data.get("customer_token") or "").strip()
    if customer_token:
        try:
            with SessionLocal() as db:
                player_id = customer_service.authenticate(
                    db,
                    customer_token,
                    update_last_seen=False,
                ).id
        except HTTPException as error:
            raise SocketSessionError("设备登录已失效", 4401) from error
    elif allow_legacy_identity and secrets.compare_digest(
        str(join_data.get("invite_code") or ""),
        legacy_invite_code,
    ):
        logger.warning("deprecated_websocket_player_id game=%s", game_type)
        player_id = str(join_data.get("player_id") or "").strip()[:100]
    else:
        raise SocketSessionError("请重新验证设备后加入房间", 4401)

    if not player_id:
        raise SocketSessionError("玩家标识不能为空", 4400)
    player_name = str(join_data.get("name") or "玩家").strip()[:20] or "玩家"
    return AuthenticatedPlayer(player_id, player_name, customer_token)


def persist_membership(setup: RoomSetup, player: AuthenticatedPlayer) -> Membership:
    """Compose seat and room-token writes using their deployed commit=False APIs."""
    try:
        with SessionLocal() as db:
            stored_player = game_persistence_service.join_game_room(
                db,
                setup.room_code,
                player.player_id,
                commit=False,
            )
            room_session = None
            if player.customer_token:
                room_session = game_persistence_service.issue_room_session_token(
                    db,
                    stored_player,
                    commit=False,
                )
            db.commit()
            players = game_persistence_service.list_game_players(db, setup.room_code)
            return Membership(players, room_session)
    except HTTPException as error:
        raise SocketSessionError(str(error.detail), 4404) from error


async def join_runtime(
    setup: RoomSetup,
    player: AuthenticatedPlayer,
    websocket,
    protocol: str,
    stored_players: list,
) -> tuple[bool, str]:
    """Restore newly persisted seats and attach one socket to the manager."""
    await game_room_manager.restore_players(setup.room_code, stored_players)
    return await game_room_manager.join(
        setup.room_code,
        player.player_id,
        player.player_name,
        websocket,
        protocol=protocol,
        game_type=setup.game_type,
    )


def sync_room_status(
    room_code: str,
    room_status: str,
    allow_restart: bool = False,
) -> None:
    """Mirror live lifecycle state without reopening a finished durable round."""
    with SessionLocal() as db:
        room = game_persistence_service.get_game_room(db, room_code)
        if room.status == "finished" and room_status != "finished" and not allow_restart:
            return
        if room.status == room_status:
            return
        game_persistence_service.update_game_room_status(db, room_code, room_status)


async def disconnect_player(
    setup: RoomSetup,
    player_id: str,
    websocket,
) -> None:
    """Detach the socket, persist reconnect grace and mirror runtime status."""
    await game_room_manager.leave(setup.room_code, player_id, websocket)
    try:
        with SessionLocal() as db:
            game_persistence_service.mark_game_player_disconnected(
                db,
                setup.room_code,
                player_id,
            )
        sync_room_status(
            setup.room_code,
            await game_room_manager.room_status(setup.room_code),
        )
    except HTTPException:
        pass


async def release_lease_if_idle(setup: RoomSetup) -> None:
    """Release the PostgreSQL lease only after the final local socket leaves."""
    if not setup.lease_acquired:
        return
    if await game_room_manager.has_live_connections(setup.room_code):
        return
    try:
        with SessionLocal() as db:
            release_room_lease(db, setup.room_code)
    except Exception:
        logger.exception("failed to release room lease room=%s", setup.room_code)
