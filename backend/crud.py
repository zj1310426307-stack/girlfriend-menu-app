import secrets
from datetime import date, datetime, time as datetime_time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

import models
import schemas
from auth import hash_token
from love_score import record_score
from task_service import complete_task_type


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

ORDER_STATUS_TRANSITIONS = {
    "待接单": {"已接单", "暂时做不了"},
    "已接单": {"制作中", "暂时做不了"},
    "制作中": {"已完成", "暂时做不了"},
    "已完成": set(),
    "暂时做不了": set(),
}


def touch_game_room(
    room: models.GameRoom,
    now: datetime | None = None,
) -> models.GameRoom:
    """Refresh one active room using status-specific retention windows."""
    now = now or datetime.now(timezone.utc)
    room.last_activity_at = now
    if room.status == "waiting":
        room.expires_at = now + WAITING_ROOM_TTL
    elif room.status == "playing":
        room.expires_at = now + PLAYING_ROOM_TTL
    else:
        room.expires_at = None
    return room


def list_games(db: Session):
    return db.query(models.Game).order_by(models.Game.id).all()


def get_game(db: Session, game_type: str):
    game = db.query(models.Game).filter(models.Game.type == game_type).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    return game


def create_game_room(db: Session, game_type: str, creator: str):
    game = get_game(db, game_type)
    if game.status != "available":
        raise HTTPException(status_code=409, detail="这个游戏还在准备中")
    creator = creator.strip()
    if not creator:
        raise HTTPException(status_code=400, detail="创建者标识不能为空")
    max_players = GAME_MAX_PLAYERS.get(game_type, 2)
    for _ in range(20):
        room_code = "".join(secrets.choice(ROOM_ALPHABET) for _ in range(6))
        if not db.query(models.GameRoom.id).filter(models.GameRoom.room_code == room_code).first():
            room = models.GameRoom(
                room_code=room_code,
                game_type=game_type,
                creator=creator,
                status="waiting",
                max_players=max_players,
            )
            touch_game_room(room)
            db.add(room)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            db.refresh(room)
            return room
    raise HTTPException(status_code=503, detail="暂时无法创建房间，请稍后再试")


def get_game_room(db: Session, room_code: str):
    room = (
        db.query(models.GameRoom)
        .filter(models.GameRoom.room_code == room_code.strip().upper())
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在或已经失效")
    return room


def update_game_room_status(db: Session, room_code: str, room_status: str):
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
    db.commit()
    db.refresh(room)
    return room


def list_game_players(db: Session, room_code: str):
    room = get_game_room(db, room_code)
    return (
        db.query(models.GamePlayer)
        .filter(models.GamePlayer.room_id == room.id)
        .order_by(models.GamePlayer.seat)
        .all()
    )


def join_game_room(db: Session, room_code: str, player_id: str):
    """Join the first free seat and return the persisted player.

    Repeated requests from the same device are idempotent. The database unique
    constraints remain the final protection if two clients race for one seat.
    """
    room = get_game_room(db, room_code)
    player_id = player_id.strip()
    if not player_id:
        raise HTTPException(status_code=400, detail="玩家标识不能为空")
    existing = (
        db.query(models.GamePlayer)
        .filter(
            models.GamePlayer.room_id == room.id,
            models.GamePlayer.player_id == player_id,
        )
        .first()
    )
    if existing:
        now = datetime.now(timezone.utc)
        existing.last_activity_at = now
        existing.disconnected_at = None
        existing.expires_at = None
        touch_game_room(room, now)
        db.commit()
        return existing
    if room.status in {"finished", "abandoned"}:
        raise HTTPException(status_code=409, detail="本房间对局已经结束")

    occupied_seats = {player.seat for player in room.players}
    available_seat = next(
        (seat for seat in range(1, room.max_players + 1) if seat not in occupied_seats),
        None,
    )
    if available_seat is None:
        raise HTTPException(status_code=409, detail="房间人数已满")

    player = models.GamePlayer(
        room_id=room.id,
        player_id=player_id,
        seat=available_seat,
        last_activity_at=datetime.now(timezone.utc),
    )
    db.add(player)
    if len(occupied_seats) + 1 >= room.max_players:
        room.status = "playing"
        room.finished_at = None
    touch_game_room(room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(models.GamePlayer)
            .filter(
                models.GamePlayer.room_id == room.id,
                models.GamePlayer.player_id == player_id,
            )
            .first()
        )
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="房间座位刚刚被其他玩家占用")
    db.refresh(player)
    if (
        player_id != room.creator
        and room.creator != "legacy_client"
        and not player_id.startswith("ai_")
    ):
        # Import locally to keep the persistence layer free of a module cycle.
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
    return player


def issue_room_session_token(db: Session, player: models.GamePlayer) -> tuple[str, datetime]:
    token = f"gfr_{secrets.token_urlsafe(36)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    player.room_session_token_hash = hash_token(token)
    player.last_activity_at = datetime.now(timezone.utc)
    player.disconnected_at = None
    player.expires_at = expires_at
    touch_game_room(player.room)
    db.commit()
    return token, expires_at


def mark_game_player_disconnected(db: Session, room_code: str, player_id: str) -> None:
    room = get_game_room(db, room_code)
    player = (
        db.query(models.GamePlayer)
        .filter(models.GamePlayer.room_id == room.id, models.GamePlayer.player_id == player_id)
        .first()
    )
    if not player:
        return
    now = datetime.now(timezone.utc)
    player.disconnected_at = now
    player.expires_at = now + timedelta(seconds=60)
    touch_game_room(room, now)
    db.commit()


def expire_stale_game_rooms(db: Session) -> list[str]:
    """Mark inactive rooms abandoned while retaining state and history."""
    now = datetime.now(timezone.utc)
    candidates = (
        db.query(models.GameRoom)
        .filter(models.GameRoom.status.in_(["waiting", "playing"]))
        .all()
    )
    rooms = []
    for room in candidates:
        expires_at = room.expires_at
        if expires_at is None:
            last_activity = room.last_activity_at or room.created_at
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            ttl = WAITING_ROOM_TTL if room.status == "waiting" else PLAYING_ROOM_TTL
            expires_at = last_activity + ttl
        elif expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            rooms.append(room)
    codes = []
    for room in rooms:
        room.status = "abandoned"
        room.abandoned_at = now
        room.finished_at = now
        room.expires_at = None
        room.owner_instance_id = None
        room.lease_expires_at = None
        room.state_version = int(room.state_version or 0) + 1
        codes.append(room.room_code)
        for player in room.players:
            player.room_session_token_hash = None
            player.expires_at = now
        db.query(models.GameReconnectToken).filter(
            models.GameReconnectToken.room_id == room.id
        ).update(
            {models.GameReconnectToken.revoked: True},
            synchronize_session=False,
        )
    if rooms:
        db.commit()
    return codes


def _game_record_query(db: Session):
    return db.query(models.GameRecord).options(
        selectinload(models.GameRecord.room).selectinload(models.GameRoom.players)
    )


def finish_game_room(
    db: Session,
    room_code: str,
    winner: str | None,
    duration: int,
    result: dict | None = None,
    round_number: int = 1,
):
    """Finish one round and persist exactly one record for that room/round.

    A client or WebSocket may retry its final message. Returning the existing
    record makes those retries safe and gives the scoring layer one stable ID.
    """
    room = get_game_room(db, room_code)
    if round_number < 1:
        raise HTTPException(status_code=422, detail="局数必须从 1 开始")
    existing = (
        _game_record_query(db)
        .filter(
            models.GameRecord.room_id == room.id,
            models.GameRecord.round_number == round_number,
        )
        .first()
    )
    if existing:
        return existing

    player_ids = {player.player_id for player in room.players}
    # V2.5 games may persist an AI winner for honest statistics. AI identities
    # never occupy a human seat and are excluded from Love Score settlement.
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
    db.add(record)
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
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            _game_record_query(db)
            .filter(
                models.GameRecord.room_id == room.id,
                models.GameRecord.round_number == round_number,
            )
            .first()
        )
        if existing:
            return existing
        raise
    return (
        _game_record_query(db)
        .filter(models.GameRecord.id == record.id)
        .one()
    )


def list_game_records(db: Session, customer_id: str, limit: int = 50):
    safe_limit = max(1, min(int(limit), 100))
    records = (
        _game_record_query(db)
        .join(models.GameRoom, models.GameRecord.room_id == models.GameRoom.id)
        .join(models.GamePlayer, models.GamePlayer.room_id == models.GameRoom.id)
        .filter(models.GamePlayer.player_id == customer_id)
        .order_by(models.GameRecord.created_at.desc(), models.GameRecord.id.desc())
        .limit(min(safe_limit * 2, 200))
        .all()
    )
    # A WebSocket round is visible only after its score/task settlement has
    # completed. Older V2.3 records have no marker and remain fully compatible.
    return [
        record
        for record in records
        if (record.result or {}).get("_settlement") != "pending"
    ][:safe_limit]


def game_stats(db: Session):
    total_games = db.query(func.count(models.GameRecord.id)).scalar() or 0
    dice_games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.game_type == "dice")
        .scalar()
        or 0
    )
    gomoku_games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.game_type == "gomoku")
        .scalar()
        or 0
    )
    flight_games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.game_type == "aeroplane")
        .scalar()
        or 0
    )
    landlord_games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.game_type == "landlord")
        .scalar()
        or 0
    )
    animal_games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.game_type == "jungle")
        .scalar()
        or 0
    )
    chess_games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.game_type == "chinese_chess")
        .scalar()
        or 0
    )
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    today_games = (
        db.query(func.count(models.GameRecord.id))
        .filter(models.GameRecord.created_at >= today_start)
        .scalar()
        or 0
    )
    all_records = db.query(models.GameRecord).all()
    def _is_ai_record(record):
        result = record.result or {}
        persisted_state = result.get("state") or {}
        return (
            record.game_type == "landlord"
            or result.get("mode") == "ai"
            or persisted_state.get("mode") == "ai"
        )

    ai_games = sum(_is_ai_record(record) for record in all_records)
    human_wins = sum(bool(record.winner) and not record.winner.startswith("ai_") for record in all_records)
    creator_gomoku_wins = (
        db.query(func.count(models.GameRecord.id))
        .join(models.GameRoom, models.GameRoom.id == models.GameRecord.room_id)
        .filter(
            models.GameRecord.game_type == "gomoku",
            models.GameRecord.winner == models.GameRoom.creator,
        )
        .scalar()
        or 0
    )
    most_played = (
        db.query(
            models.GameRecord.game_type,
            func.count(models.GameRecord.id).label("play_count"),
        )
        .group_by(models.GameRecord.game_type)
        .order_by(func.count(models.GameRecord.id).desc(), models.GameRecord.game_type)
        .first()
    )
    most_played_game = None
    if most_played:
        game = db.query(models.Game).filter(models.Game.type == most_played.game_type).first()
        most_played_game = game.name if game else most_played.game_type
    game_names = {game.type: game.name for game in db.query(models.Game).all()}
    popular_games = [
        {
            "game_type": game_type,
            "name": game_names.get(game_type, game_type),
            "count": int(count),
        }
        for game_type, count in (
            db.query(models.GameRecord.game_type, func.count(models.GameRecord.id))
            .group_by(models.GameRecord.game_type)
            .order_by(func.count(models.GameRecord.id).desc(), models.GameRecord.game_type)
            .limit(5)
            .all()
        )
    ]

    love_score_change = (
        db.query(func.sum(models.LoveScore.score))
        .filter(
            or_(
                models.LoveScore.type.in_(("GAME_PLAY", "GAME_WIN", "GAME_EVENT", "GAME_BONUS", "ACHIEVEMENT", "LOVE_TASK")),
                and_(
                    models.LoveScore.type == "SPECIAL_EVENT",
                    models.LoveScore.description == "五子棋三连胜",
                ),
            )
        )
        .scalar()
        or 0
    )
    interaction_count = (
        db.query(func.count(models.GameEventLog.id))
        .filter(models.GameEventLog.status == "completed")
        .scalar()
        or 0
    )
    completed_tasks = (
        db.query(func.count(models.DailyTask.id))
        .filter(models.DailyTask.status == "completed")
        .scalar()
        or 0
    )
    achievement_unlocks = db.query(func.count(models.UserAchievement.id)).scalar() or 0
    today = datetime.now().date()
    growth_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    growth_entries = (
        db.query(models.LoveScore.created_at, models.LoveScore.score)
        .filter(models.LoveScore.created_at >= growth_start)
        .all()
    )
    growth_by_day = {today - timedelta(days=offset): 0 for offset in range(6, -1, -1)}
    for created_at, score in growth_entries:
        growth_by_day[created_at.date()] = growth_by_day.get(created_at.date(), 0) + int(score)
    return {
        "total_games": int(total_games),
        "dice_games": int(dice_games),
        "gomoku_games": int(gomoku_games),
        "flight_games": int(flight_games),
        "landlord_games": int(landlord_games),
        "animal_games": int(animal_games),
        "chess_games": int(chess_games),
        "today_games": int(today_games),
        "ai_games": int(ai_games),
        "gomoku_win_rate": round(
            creator_gomoku_wins * 100 / gomoku_games,
            1,
        )
        if gomoku_games
        else 0.0,
        "player_win_rate": round(human_wins * 100 / total_games, 1) if total_games else 0.0,
        "most_played_game": most_played_game,
        "popular_games": popular_games,
        "love_score_change": int(love_score_change),
        "interaction_count": int(interaction_count),
        "completed_tasks": int(completed_tasks),
        "achievement_unlocks": int(achievement_unlocks),
        "love_score_growth": [
            {"date": day.isoformat(), "score": score}
            for day, score in sorted(growth_by_day.items())
        ],
    }


def list_dishes(db: Session, category: str | None = None):
    query = db.query(models.Dish).filter(models.Dish.is_active.is_(True))
    if category:
        query = query.filter(models.Dish.category == category)
    return query.order_by(models.Dish.id.desc()).all()


def get_dish(db: Session, dish_id: int):
    dish = (
        db.query(models.Dish)
        .filter(models.Dish.id == dish_id, models.Dish.is_active.is_(True))
        .first()
    )
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")
    return dish


def create_dish(db: Session, data: schemas.DishCreate):
    dish = models.Dish(**data.model_dump())
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return dish


def update_dish(db: Session, dish_id: int, data: schemas.DishUpdate):
    dish = get_dish(db, dish_id)
    for key, value in data.model_dump().items():
        setattr(dish, key, value)
    db.commit()
    db.refresh(dish)
    return dish


def delete_dish(db: Session, dish_id: int):
    dish = get_dish(db, dish_id)
    # Keep historical order items intact. A physical delete can fail on
    # PostgreSQL once the dish has been ordered because of the foreign key.
    dish.is_active = False
    db.commit()


def list_favorite_dishes(db: Session, customer_id: str):
    return (
        db.query(models.Dish)
        .join(models.FavoriteDish, models.FavoriteDish.dish_id == models.Dish.id)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.Dish.is_active.is_(True),
        )
        .order_by(models.FavoriteDish.created_at.desc())
        .all()
    )


def add_favorite_dish(db: Session, customer_id: str, dish_id: int):
    dish = get_dish(db, dish_id)
    existing = (
        db.query(models.FavoriteDish)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.FavoriteDish.dish_id == dish_id,
        )
        .first()
    )
    if existing:
        return dish
    db.add(models.FavoriteDish(customer_id=customer_id, dish_id=dish_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return dish


def remove_favorite_dish(db: Session, customer_id: str, dish_id: int):
    favorite = (
        db.query(models.FavoriteDish)
        .filter(
            models.FavoriteDish.customer_id == customer_id,
            models.FavoriteDish.dish_id == dish_id,
        )
        .first()
    )
    if favorite:
        db.delete(favorite)
        db.commit()


def create_order(db: Session, data: schemas.OrderCreate):
    if data.idempotency_key:
        existing = (
            db.query(models.Order)
            .filter(models.Order.idempotency_key == data.idempotency_key)
            .first()
        )
        if existing:
            if existing.customer_id != data.customer_id:
                raise HTTPException(status_code=409, detail="提交标识已经被使用")
            return existing
    dish_ids = {item.dish_id for item in data.items}
    dishes = (
        db.query(models.Dish)
        .filter(models.Dish.id.in_(dish_ids), models.Dish.is_active.is_(True))
        .all()
    )
    dish_map = {dish.id: dish for dish in dishes}
    missing = dish_ids - dish_map.keys()
    if missing:
        raise HTTPException(status_code=400, detail=f"菜品不存在或已经下架：{sorted(missing)}")

    if data.source_order_id:
        source_order = get_order(db, data.source_order_id)
        if not data.customer_id or source_order.customer_id != data.customer_id:
            raise HTTPException(status_code=404, detail="订单不存在")

    order = models.Order(
        note=data.note,
        desired_time=data.desired_time,
        desired_at=(
            data.desired_at.replace(tzinfo=timezone.utc)
            if data.desired_at and data.desired_at.tzinfo is None
            else data.desired_at.astimezone(timezone.utc) if data.desired_at else None
        ),
        customer_id=data.customer_id,
        source_order_id=data.source_order_id,
        idempotency_key=data.idempotency_key,
        status_updated_at=datetime.now(timezone.utc),
    )
    db.add(order)
    db.flush()
    for item in data.items:
        dish = dish_map[item.dish_id]
        order.items.append(
            models.OrderItem(
                dish_id=dish.id,
                dish_name=dish.name,
                price=dish.price,
                quantity=item.quantity,
            )
        )
    db.commit()
    db.refresh(order)
    if order.source_order_id and order.customer_id:
        record_score(
            db,
            order.customer_id,
            "SPECIAL_EVENT",
            2,
            "再次点了喜欢的菜单",
            order.id,
        )
    return order


def repeat_order_draft(db: Session, order_id: int, customer_id: str):
    """Build an editable cart draft without creating a submitted order."""
    order = get_order(db, order_id)
    if not order.customer_id or order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="订单不存在")

    dish_ids = {item.dish_id for item in order.items}
    current_dishes = db.query(models.Dish).filter(models.Dish.id.in_(dish_ids)).all()
    dish_map = {dish.id: dish for dish in current_dishes}
    items = []
    unavailable_names = []
    for item in order.items:
        dish = dish_map.get(item.dish_id)
        available = bool(dish and dish.is_active)
        if not available:
            unavailable_names.append(item.dish_name)
        items.append(
            {
                "dish_id": item.dish_id,
                "name": dish.name if dish else item.dish_name,
                "description": dish.description if dish else "",
                "category": dish.category if dish else "",
                "price": dish.price if dish else item.price,
                "image_url": dish.image_url if dish else "",
                "quantity": item.quantity,
                "available": available,
            }
        )
    return {
        "source_order_id": order.id,
        "note": order.note,
        "items": items,
        "unavailable_names": unavailable_names,
    }


def list_orders(db: Session):
    return db.query(models.Order).order_by(models.Order.created_at.desc()).all()


def list_admin_orders(
    db: Session,
    status: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    safe_limit = max(1, min(int(limit), 50))
    query = db.query(models.Order)
    count_query = db.query(func.count(models.Order.id))
    filters = []
    if status:
        filters.append(models.Order.status == status)
    if cursor:
        filters.append(models.Order.id < cursor)
    if start_date:
        filters.append(models.Order.created_at >= datetime.combine(start_date, datetime_time.min))
    if end_date:
        filters.append(models.Order.created_at < datetime.combine(end_date + timedelta(days=1), datetime_time.min))
    if keyword and keyword.strip():
        value = keyword.strip()
        keyword_filter = models.Order.items.any(models.OrderItem.dish_name.ilike(f"%{value}%"))
        if value.isdigit():
            keyword_filter = or_(models.Order.id == int(value), keyword_filter)
        filters.append(keyword_filter)
    if filters:
        query = query.filter(*filters)
        count_query = count_query.filter(*filters)
    items = query.order_by(models.Order.id.desc()).limit(safe_limit + 1).all()
    has_more = len(items) > safe_limit
    visible = items[:safe_limit]
    return {
        "items": visible,
        "next_cursor": visible[-1].id if has_more and visible else None,
        "total_estimate": count_query.scalar() or 0,
    }


def list_customer_orders(db: Session, customer_id: str):
    return (
        db.query(models.Order)
        .filter(models.Order.customer_id == customer_id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


def get_order(db: Session, order_id: int):
    order = db.get(models.Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


def update_order_status(db: Session, order_id: int, status: str, actor_id: str = "admin"):
    order = get_order(db, order_id)
    if status == order.status:
        return order
    if status not in ORDER_STATUS_TRANSITIONS.get(order.status, set()):
        raise HTTPException(status_code=409, detail=f"订单不能从“{order.status}”直接变为“{status}”")
    previous = order.status
    order.status = status
    order.status_updated_at = datetime.now(timezone.utc)
    db.add(models.OrderStatusEvent(
        order_id=order.id,
        from_status=previous,
        to_status=status,
        actor_type="ADMIN",
        actor_id=actor_id,
    ))
    db.commit()
    db.refresh(order)
    if status == "已完成" and order.customer_id:
        record_score(
            db,
            order.customer_id,
            "ORDER_COMPLETE",
            10,
            "完成一次晚餐制作",
            order.id,
        )
        complete_task_type(db, order.customer_id, "MEAL")
    return order


def rollback_order_status(db: Session, order_id: int, actor_id: str = "admin"):
    order = get_order(db, order_id)
    if order.status == "已完成":
        raise HTTPException(status_code=409, detail="已完成订单禁止回退，原评价会被完整保留")
    event = (
        db.query(models.OrderStatusEvent)
        .filter(models.OrderStatusEvent.order_id == order.id)
        .order_by(models.OrderStatusEvent.id.desc())
        .first()
    )
    if not event or not event.from_status:
        raise HTTPException(status_code=409, detail="没有可以撤回的上一步")
    previous = order.status
    order.status = event.from_status
    order.status_updated_at = datetime.now(timezone.utc)
    db.add(models.OrderStatusEvent(
        order_id=order.id,
        from_status=previous,
        to_status=order.status,
        actor_type="ADMIN_ROLLBACK",
        actor_id=actor_id,
    ))
    db.commit()
    db.refresh(order)
    return order


def get_review(db: Session, order_id: int):
    get_order(db, order_id)
    review = (
        db.query(models.Review)
        .filter(models.Review.order_id == order_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="该订单还没有评价")
    return review


def create_review(db: Session, order_id: int, data: schemas.ReviewCreate):
    order = get_order(db, order_id)
    if order.status != "已完成":
        raise HTTPException(status_code=400, detail="订单完成后才能评价")
    if order.review:
        raise HTTPException(status_code=409, detail="该订单已经评价过了")

    review = models.Review(order_id=order_id, **data.model_dump())
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该订单已经评价过了")
    db.refresh(review)
    if review.rating == 5 and order.customer_id:
        record_score(
            db,
            order.customer_id,
            "ORDER_REVIEW",
            5,
            "完成一次五星评价",
            order.id,
        )
        complete_task_type(db, order.customer_id, "REVIEW")
    return review


def get_stats_summary(db: Session):
    total_orders = db.query(func.count(models.Order.id)).scalar() or 0
    completed_orders = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.status == "已完成")
        .scalar()
        or 0
    )
    last_order_at = db.query(func.max(models.Order.created_at)).scalar()
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "last_order_at": last_order_at,
    }


def get_dish_stats(db: Session):
    rows = (
        db.query(
            models.OrderItem.dish_id,
            models.OrderItem.dish_name,
            func.sum(models.OrderItem.quantity).label("total_quantity"),
            func.max(models.Order.created_at).label("last_ordered_at"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .group_by(models.OrderItem.dish_id, models.OrderItem.dish_name)
        .order_by(
            func.sum(models.OrderItem.quantity).desc(),
            func.max(models.Order.created_at).desc(),
        )
        .all()
    )
    return [
        {
            "dish_id": row.dish_id,
            "dish_name": row.dish_name,
            "total_quantity": row.total_quantity,
            "last_ordered_at": row.last_ordered_at,
        }
        for row in rows
    ]


def get_recent_orders(db: Session):
    return (
        db.query(models.Order)
        .order_by(models.Order.created_at.desc())
        .limit(10)
        .all()
    )


def get_favorite_ranking(db: Session, customer_id: str, limit: int = 5):
    """Rank this device's dishes from submitted orders, reviews and favorites.

    A review belongs to an order, so its rating contributes to every dish in that
    order. Repeat orders receive a modest boost without overwhelming actual order
    frequency. This keeps the ranking useful even before many reviews exist.
    """
    rows = (
        db.query(
            models.Dish.id.label("dish_id"),
            models.Dish.name.label("name"),
            func.sum(models.OrderItem.quantity).label("count"),
            func.avg(models.Review.rating).label("rating"),
        )
        .join(models.OrderItem, models.OrderItem.dish_id == models.Dish.id)
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .outerjoin(models.Review, models.Review.order_id == models.Order.id)
        .filter(
            models.Order.customer_id == customer_id,
            models.Dish.is_active.is_(True),
        )
        .group_by(models.Dish.id, models.Dish.name)
        .all()
    )
    repeat_rows = (
        db.query(
            models.OrderItem.dish_id,
            func.count(func.distinct(models.Order.id)).label("repeat_count"),
        )
        .join(models.Order, models.Order.id == models.OrderItem.order_id)
        .filter(
            models.Order.customer_id == customer_id,
            models.Order.source_order_id.is_not(None),
        )
        .group_by(models.OrderItem.dish_id)
        .all()
    )
    repeat_counts = {row.dish_id: int(row.repeat_count or 0) for row in repeat_rows}
    favorite_ids = {
        row.dish_id
        for row in db.query(models.FavoriteDish.dish_id)
        .filter(models.FavoriteDish.customer_id == customer_id)
        .all()
    }

    ranking = []
    for row in rows:
        count = int(row.count or 0)
        rating = round(float(row.rating), 1) if row.rating is not None else None
        repeat_count = repeat_counts.get(row.dish_id, 0)
        is_favorite = row.dish_id in favorite_ids
        rating_basis = rating if rating is not None else 3.0
        score = rating_basis * count * (1 + repeat_count * 0.25)
        if is_favorite:
            score += 2
        ranking.append(
            {
                "dish_id": row.dish_id,
                "name": row.name,
                "count": count,
                "rating": rating,
                "repeat_count": repeat_count,
                "is_favorite": is_favorite,
                "score": round(score, 2),
            }
        )

    ranking.sort(key=lambda item: (item["score"], item["count"]), reverse=True)
    return ranking[:limit]
