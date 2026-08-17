from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

import models
import schemas
from services import (
    dish_service,
    favorite_service,
    game_persistence_service,
    order_service,
    review_service,
    stats_service,
)


def touch_game_room(
    room: models.GameRoom,
    now: datetime | None = None,
) -> models.GameRoom:
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.touch_game_room(room, now)


def list_games(db: Session):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.list_games(db)


def get_game(db: Session, game_type: str):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.get_game(db, game_type)


def create_game_room(db: Session, game_type: str, creator: str):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.create_game_room(db, game_type, creator)


def get_game_room(db: Session, room_code: str):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.get_game_room(db, room_code)


def get_game_room_runtime(db: Session, room_code: str):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.get_game_room_runtime(db, room_code)


def update_game_room_status(db: Session, room_code: str, room_status: str):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.update_game_room_status(
        db,
        room_code,
        room_status,
    )


def list_game_players(db: Session, room_code: str):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.list_game_players(db, room_code)


def join_game_room(
    db: Session,
    room_code: str,
    player_id: str,
    *,
    commit: bool = True,
):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.join_game_room(
        db,
        room_code,
        player_id,
        commit=commit,
    )


def issue_room_session_token(
    db: Session,
    player: models.GamePlayer,
    *,
    commit: bool = True,
) -> tuple[str, datetime]:
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.issue_room_session_token(
        db,
        player,
        commit=commit,
    )


def mark_game_player_disconnected(db: Session, room_code: str, player_id: str) -> None:
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.mark_game_player_disconnected(
        db,
        room_code,
        player_id,
    )


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
            ttl = (
                game_persistence_service.WAITING_ROOM_TTL
                if room.status == "waiting"
                else game_persistence_service.PLAYING_ROOM_TTL
            )
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


def finish_game_room(
    db: Session,
    room_code: str,
    winner: str | None,
    duration: int,
    result: dict | None = None,
    round_number: int = 1,
):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.finish_game_room(
        db,
        room_code,
        winner,
        duration,
        result,
        round_number,
    )


def list_game_records(db: Session, customer_id: str, limit: int = 50):
    """Compatibility facade; migrate callers before removal."""
    return game_persistence_service.list_game_records(db, customer_id, limit)


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
    """Compatibility facade; migrate callers before removal."""
    return dish_service.list_dishes(db, category)


def get_dish(db: Session, dish_id: int):
    """Compatibility facade; migrate callers before removal."""
    return dish_service.get_dish(db, dish_id)


def create_dish(db: Session, data: schemas.DishCreate):
    """Compatibility facade; migrate callers before removal."""
    return dish_service.create_dish(db, data)


def update_dish(db: Session, dish_id: int, data: schemas.DishUpdate):
    """Compatibility facade; migrate callers before removal."""
    return dish_service.update_dish(db, dish_id, data)


def delete_dish(db: Session, dish_id: int):
    """Compatibility facade; migrate callers before removal."""
    return dish_service.delete_dish(db, dish_id)


def list_favorite_dishes(db: Session, customer_id: str):
    """Compatibility facade; migrate callers before removal."""
    return favorite_service.list_favorite_dishes(db, customer_id)


def add_favorite_dish(db: Session, customer_id: str, dish_id: int):
    """Compatibility facade; migrate callers before removal."""
    return favorite_service.add_favorite_dish(db, customer_id, dish_id)


def remove_favorite_dish(db: Session, customer_id: str, dish_id: int):
    """Compatibility facade; migrate callers before removal."""
    return favorite_service.remove_favorite_dish(db, customer_id, dish_id)


def create_order(db: Session, data: schemas.OrderCreate):
    """Compatibility facade; migrate callers before removal."""
    return order_service.create_order(db, data)


def repeat_order_draft(db: Session, order_id: int, customer_id: str):
    """Compatibility facade; migrate callers before removal."""
    return order_service.repeat_order_draft(db, order_id, customer_id)


def list_orders(db: Session):
    """Compatibility facade; migrate callers before removal."""
    return order_service.list_orders(db)


def list_admin_orders(
    db: Session,
    status: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
    keyword: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Compatibility facade; migrate callers before removal."""
    return order_service.list_admin_orders(
        db,
        status,
        cursor,
        limit,
        keyword,
        start_date,
        end_date,
    )


def list_customer_orders(db: Session, customer_id: str):
    """Compatibility facade; migrate callers before removal."""
    return order_service.list_customer_orders(db, customer_id)


def get_order(db: Session, order_id: int):
    """Compatibility facade; migrate callers before removal."""
    return order_service.get_order(db, order_id)


def update_order_status(db: Session, order_id: int, status: str, actor_id: str = "admin"):
    """Compatibility facade; migrate callers before removal."""
    return order_service.update_order_status(db, order_id, status, actor_id)


def rollback_order_status(db: Session, order_id: int, actor_id: str = "admin"):
    """Compatibility facade; migrate callers before removal."""
    return order_service.rollback_order_status(db, order_id, actor_id)


def get_review(db: Session, order_id: int):
    """Compatibility facade; migrate callers before removal."""
    return review_service.get_review(db, order_id)


def create_review(db: Session, order_id: int, data: schemas.ReviewCreate):
    """Compatibility facade; migrate callers before removal."""
    return review_service.create_review(db, order_id, data)


def get_stats_summary(db: Session):
    """Compatibility facade; migrate callers before removal."""
    return stats_service.get_stats_summary(db)


def get_dish_stats(db: Session):
    """Compatibility facade; migrate callers before removal."""
    return stats_service.get_dish_stats(db)


def get_recent_orders(db: Session):
    """Compatibility facade; migrate callers before removal."""
    return stats_service.get_recent_orders(db)


def get_favorite_ranking(db: Session, customer_id: str, limit: int = 5):
    """Compatibility facade for the ranking service used by legacy callers."""
    return favorite_service.rank_favorite_dishes(db, customer_id, limit)
