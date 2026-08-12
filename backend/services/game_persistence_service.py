"""Durable game catalogue, room, membership and record orchestration.

The service preserves deployed transaction and compatibility semantics while
keeping WebSocket transport, live state, lease ownership and settlement rewards
outside this boundary.
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from auth import hash_token
from repositories import game_runtime as game_runtime_repository


ROOM_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
WAITING_ROOM_TTL = timedelta(minutes=30)
PLAYING_ROOM_TTL = timedelta(hours=6)
GAME_MAX_PLAYERS = {
    "dice": 2,
    "gomoku": 2,
    "aeroplane": 2,
    "landlord": 3,
    "jungle": 2,
    "chinese_chess": 2,
}


def touch_game_room(
    room: models.GameRoom,
    now: datetime | None = None,
) -> models.GameRoom:
    """Refresh an active room using the existing status-specific retention TTL."""
    now = now or datetime.now(timezone.utc)
    room.last_activity_at = now
    if room.status == "waiting":
        room.expires_at = now + WAITING_ROOM_TTL
    elif room.status == "playing":
        room.expires_at = now + PLAYING_ROOM_TTL
    else:
        room.expires_at = None
    return room


def list_games(db: Session) -> list[models.Game]:
    """Return the durable game catalogue without runtime state."""
    return game_runtime_repository.list_catalog(db)


def get_game(db: Session, game_type: str) -> models.Game:
    """Return one game catalogue row or preserve its established 404."""
    game = game_runtime_repository.find_game(db, game_type)
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    return game


def create_game_room(
    db: Session,
    game_type: str,
    creator: str,
) -> models.GameRoom:
    """Validate a catalogue entry and create a collision-safe six-character room."""
    game = get_game(db, game_type)
    if game.status != "available":
        raise HTTPException(status_code=409, detail="这个游戏还在准备中")
    creator = creator.strip()
    if not creator:
        raise HTTPException(status_code=400, detail="创建者标识不能为空")
    max_players = GAME_MAX_PLAYERS.get(game_type, 2)
    for _ in range(20):
        room_code = "".join(secrets.choice(ROOM_ALPHABET) for _ in range(6))
        if game_runtime_repository.room_code_exists(db, room_code):
            continue
        room = models.GameRoom(
            room_code=room_code,
            game_type=game_type,
            creator=creator,
            status="waiting",
            max_players=max_players,
        )
        touch_game_room(room)
        try:
            return game_runtime_repository.create_room(db, room)
        except IntegrityError:
            continue
    raise HTTPException(status_code=503, detail="暂时无法创建房间，请稍后再试")


def get_game_room(db: Session, room_code: str) -> models.GameRoom:
    """Return response-ready durable room metadata or the established 404."""
    room = game_runtime_repository.find_room(db, room_code)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在或已经失效")
    return room


def get_game_room_runtime(db: Session, room_code: str) -> models.GameRoom:
    """Return relationship-free metadata for the latency-sensitive gateway."""
    room = game_runtime_repository.find_room_runtime(db, room_code)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在或已经失效")
    return room


def update_game_room_status(
    db: Session,
    room_code: str,
    room_status: str,
) -> models.GameRoom:
    """Persist one runtime status/version mutation with existing timestamp rules."""
    room = get_game_room(db, room_code)
    room.state_version = int(room.state_version or 0) + 1
    if room.status != room_status:
        room.status = room_status
        if room_status == "finished":
            room.finished_at = datetime.now()
        elif room_status == "playing":
            room.finished_at = None
            room.abandoned_at = None
    touch_game_room(room)
    return game_runtime_repository.save_room(db, room)


def list_game_players(db: Session, room_code: str) -> list[models.GamePlayer]:
    """Return ordered durable seats or preserve the missing-room 404."""
    players = game_runtime_repository.list_players(db, room_code)
    if players is None:
        raise HTTPException(status_code=404, detail="房间不存在或已经失效")
    return players


def _notify_joined_players(
    db: Session,
    room: models.GameRoom,
    player_id: str,
) -> None:
    """Preserve the existing post-membership notification orchestration."""
    if (
        player_id == room.creator
        or room.creator == "legacy_client"
        or player_id.startswith("ai_")
    ):
        return
    # Kept in the Service to avoid coupling the Repository to another domain.
    from notification_service import create_notification

    create_notification(
        db,
        room.creator,
        "GAME_JOINED",
        "对方已经加入游戏",
        f"房间 {room.room_code} 已经可以开始。",
        room.id,
    )
    create_notification(
        db,
        player_id,
        "GAME_STARTED",
        "双人房间准备好了",
        f"房间 {room.room_code} 等你一起玩。",
        room.id,
    )


def join_game_room(
    db: Session,
    room_code: str,
    player_id: str,
    *,
    commit: bool = True,
) -> models.GamePlayer:
    """Idempotently occupy the first free seat using an explicit commit boundary."""
    room = game_runtime_repository.find_room_with_players(db, room_code)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在或已经失效")
    player_id = player_id.strip()
    if not player_id:
        raise HTTPException(status_code=400, detail="玩家标识不能为空")
    existing = game_runtime_repository.find_player(db, room.id, player_id)
    if existing:
        # ``find_room_with_players`` intentionally disables unrelated lazy loads,
        # so a separately queried existing seat has no ``room`` relationship.
        # Reattach the room before the caller composes room-session issuance in
        # the same transaction; otherwise reconnecting players crash while the
        # room TTL is refreshed.
        existing.room = room
        now = datetime.now(timezone.utc)
        existing.last_activity_at = now
        existing.disconnected_at = None
        existing.expires_at = None
        touch_game_room(room, now)
        return game_runtime_repository.save_player_activity(
            db,
            existing,
            commit=commit,
        )
    if room.status in {"finished", "abandoned"}:
        raise HTTPException(status_code=409, detail="本房间对局已经结束")

    occupied_seats = {player.seat for player in room.players}
    available_seat = next(
        (
            seat
            for seat in range(1, room.max_players + 1)
            if seat not in occupied_seats
        ),
        None,
    )
    if available_seat is None:
        raise HTTPException(status_code=409, detail="房间人数已满")

    player = models.GamePlayer(
        room=room,
        player_id=player_id,
        seat=available_seat,
        last_activity_at=datetime.now(timezone.utc),
    )
    if len(occupied_seats) + 1 >= room.max_players:
        room.status = "playing"
        room.finished_at = None
    touch_game_room(room)
    try:
        player = game_runtime_repository.save_player(db, player, commit=commit)
    except IntegrityError as error:
        existing = game_runtime_repository.find_player(db, room.id, player_id)
        if existing:
            existing.room = room
            return existing
        raise HTTPException(
            status_code=409,
            detail="房间座位刚刚被其他玩家占用",
        ) from error
    _notify_joined_players(db, room, player_id)
    return player


def issue_room_session_token(
    db: Session,
    player: models.GamePlayer,
    *,
    commit: bool = True,
) -> tuple[str, datetime]:
    """Return a raw token once while persisting only its hash and expiry."""
    token = f"gfr_{secrets.token_urlsafe(36)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    player.room_session_token_hash = hash_token(token)
    player.last_activity_at = datetime.now(timezone.utc)
    player.disconnected_at = None
    player.expires_at = expires_at
    touch_game_room(player.room)
    game_runtime_repository.save_room_session(db, player, commit=commit)
    return token, expires_at


def mark_game_player_disconnected(
    db: Session,
    room_code: str,
    player_id: str,
) -> None:
    """Persist the existing sixty-second reconnect grace period when seated."""
    room = get_game_room(db, room_code)
    player = game_runtime_repository.find_player(db, room.id, player_id)
    if not player:
        return
    now = datetime.now(timezone.utc)
    player.disconnected_at = now
    player.expires_at = now + timedelta(seconds=60)
    touch_game_room(room, now)
    game_runtime_repository.save_disconnect(db)


def finish_game_room(
    db: Session,
    room_code: str,
    winner: str | None,
    duration: int,
    result: dict | None = None,
    round_number: int = 1,
) -> models.GameRecord:
    """Persist exactly one pending-settlement record for a durable room round."""
    room = get_game_room(db, room_code)
    if round_number < 1:
        raise HTTPException(status_code=422, detail="局数必须从 1 开始")
    existing = game_runtime_repository.find_round_record(
        db,
        room.id,
        round_number,
    )
    if existing:
        return existing

    player_ids = {player.player_id for player in room.players}
    if winner is not None and winner not in player_ids and not winner.startswith("ai_"):
        raise HTTPException(status_code=400, detail="获胜者不是本房间玩家")

    record = models.GameRecord(
        room_id=room.id,
        round_number=round_number,
        game_type=room.game_type,
        winner=winner,
        duration=max(0, int(duration)),
        result=result or {},
        settlement_status="pending",
        settlement_attempts=0,
    )
    if winner:
        winner_player = next(
            (player for player in room.players if player.player_id == winner),
            None,
        )
        if winner_player:
            winner_player.score += 1
    room.status = "finished"
    room.finished_at = datetime.now()
    room.expires_at = None
    room.owner_instance_id = None
    room.lease_expires_at = None
    try:
        return game_runtime_repository.create_record(db, record)
    except IntegrityError:
        existing = game_runtime_repository.find_round_record(
            db,
            room.id,
            round_number,
        )
        if existing:
            return existing
        raise


def list_game_records(
    db: Session,
    customer_id: str,
    limit: int = 50,
) -> list[models.GameRecord]:
    """Return member-visible records while hiding pending WebSocket settlement."""
    safe_limit = max(1, min(int(limit), 100))
    records = game_runtime_repository.list_records_for_player(
        db,
        customer_id,
        min(safe_limit * 2, 200),
    )
    return [
        record
        for record in records
        if (record.result or {}).get("_settlement") != "pending"
    ][:safe_limit]
