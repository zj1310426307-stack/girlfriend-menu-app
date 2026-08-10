"""Rankings, AI catalog, private memories and explainable daily summaries."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models


AI_CATALOG = (
    ("chinese_chess", "random", "象棋练习生", {"style": "random"}),
    ("chinese_chess", "rule", "象棋陪练官", {"style": "capture_check"}),
    ("jungle", "random", "森林新手", {"style": "random"}),
    ("jungle", "rule", "森林向导", {"style": "rule"}),
    ("landlord", "random", "牌桌新手", {"style": "random"}),
    ("landlord", "rule", "牌桌搭档", {"style": "rule"}),
    ("aeroplane", "random", "飞行棋新手", {"style": "random"}),
    ("aeroplane", "rule", "飞行棋领航员", {"style": "rule"}),
    ("gomoku", "random", "五子棋新手", {"style": "random"}),
    ("gomoku", "rule", "五子棋陪练", {"style": "rule"}),
    ("gomoku", "strategy", "五子棋挑战者", {"style": "strategy"}),
)


def ensure_ai_catalog(db: Session) -> list[models.AIPlayer]:
    """Idempotently seed personas for databases created without Alembic."""
    existing = {(row.game_type, row.level) for row in db.query(models.AIPlayer).all()}
    for game_type, level, name, config in AI_CATALOG:
        if (game_type, level) not in existing:
            db.add(models.AIPlayer(game_type=game_type, level=level, name=name, config=config))
    db.commit()
    return db.query(models.AIPlayer).filter(models.AIPlayer.enabled.is_(True)).order_by(models.AIPlayer.game_type, models.AIPlayer.level).all()


def rebuild_statistics(db: Session) -> None:
    """Rebuild materialized player totals from immutable completed game records."""
    aggregates: dict[tuple[str, str], dict] = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "draws": 0})
    records = db.query(models.GameRecord).all()
    players_by_room: dict[int, list[str]] = defaultdict(list)
    for player in db.query(models.GamePlayer).all():
        if player.player_id.startswith("ai_"):
            continue
        players_by_room[player.room_id].append(player.player_id)
    for record in records:
        for player_id in players_by_room.get(record.room_id, []):
            row = aggregates[(player_id, record.game_type)]
            row["total"] += 1
            if not record.winner:
                row["draws"] += 1
            elif record.winner == player_id:
                row["wins"] += 1
            else:
                row["losses"] += 1
    existing = {(row.player_id, row.game_type): row for row in db.query(models.GameStatistic).all()}
    for key, values in aggregates.items():
        row = existing.get(key) or models.GameStatistic(player_id=key[0], game_type=key[1])
        if row.id is None:
            db.add(row)
        row.total_games = values["total"]
        row.wins = values["wins"]
        row.losses = values["losses"]
        row.draws = values["draws"]
        row.win_rate = round(values["wins"] * 100 / values["total"], 1) if values["total"] else 0
        row.updated_at = datetime.now()
    for key, row in existing.items():
        if key not in aggregates:
            db.delete(row)
    db.commit()


def ranking(db: Session, customer_id: str) -> dict:
    """Return personal totals and a monthly leaderboard scoped to shared rooms."""
    rebuild_statistics(db)
    my_rows = db.query(models.GameStatistic).filter(models.GameStatistic.player_id == customer_id).order_by(models.GameStatistic.total_games.desc()).all()
    since = datetime.combine(date.today().replace(day=1), time.min)
    my_room_ids = {row[0] for row in db.query(models.GamePlayer.room_id).filter(models.GamePlayer.player_id == customer_id)}
    monthly = defaultdict(lambda: {"games": 0, "wins": 0})
    popular = Counter()
    if my_room_ids:
        records = db.query(models.GameRecord).filter(models.GameRecord.room_id.in_(my_room_ids), models.GameRecord.created_at >= since).all()
        room_players = defaultdict(list)
        for player in db.query(models.GamePlayer).filter(models.GamePlayer.room_id.in_(my_room_ids)).all():
            if player.player_id.startswith("ai_"):
                continue
            room_players[player.room_id].append(player.player_id)
        for record in records:
            popular[record.game_type] += 1
            for player_id in room_players[record.room_id]:
                monthly[player_id]["games"] += 1
                monthly[player_id]["wins"] += int(record.winner == player_id)
    ordered = sorted(monthly.items(), key=lambda item: (-item[1]["wins"], -item[1]["games"], item[0]))
    entries = []
    for rank, (player_id, values) in enumerate(ordered[:20], 1):
        entries.append({
            "rank": rank,
            "display_name": "我" if player_id == customer_id else f"搭档·{player_id[-4:]}",
            "total_games": values["games"],
            "wins": values["wins"],
            "win_rate": round(values["wins"] * 100 / values["games"], 1) if values["games"] else 0,
        })
    return {
        "my_statistics": [{"game_type": row.game_type, "total_games": row.total_games, "wins": row.wins, "losses": row.losses, "draws": row.draws, "win_rate": row.win_rate} for row in my_rows],
        "monthly_ranking": entries,
        "popular_games": [{"game_type": game, "count": count} for game, count in popular.most_common()],
    }


def add_memory(db: Session, customer_id: str, game_type: str, event: str, content: str, related_id: int = 0) -> None:
    """Insert one idempotent private memory without interrupting settlement."""
    existing = db.query(models.GameMemory.id).filter(models.GameMemory.customer_id == customer_id, models.GameMemory.game_type == game_type, models.GameMemory.event == event, models.GameMemory.related_id == related_id).first()
    if existing:
        return
    db.add(models.GameMemory(customer_id=customer_id, game_type=game_type, event=event, content=content, related_id=related_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def list_memories(db: Session, customer_id: str, limit: int = 50) -> list[models.GameMemory]:
    """Return only memories owned by the current device identity."""
    return db.query(models.GameMemory).filter(models.GameMemory.customer_id == customer_id).order_by(models.GameMemory.created_at.desc(), models.GameMemory.id.desc()).limit(max(1, min(limit, 100))).all()


def daily_summary(db: Session, customer_id: str) -> dict:
    """Build a transparent rule-based daily summary from food, games and scores."""
    start = datetime.combine(date.today(), time.min)
    meals = db.query(func.count(models.Order.id)).filter(models.Order.customer_id == customer_id, models.Order.status == "已完成", models.Order.created_at >= start).scalar() or 0
    games = db.query(func.count(models.GameRecord.id)).join(models.GamePlayer, models.GamePlayer.room_id == models.GameRecord.room_id).filter(models.GamePlayer.player_id == customer_id, models.GameRecord.created_at >= start).scalar() or 0
    score_change = db.query(func.coalesce(func.sum(models.LoveScore.score), 0)).filter(models.LoveScore.customer_id == customer_id, models.LoveScore.created_at >= start).scalar() or 0
    favorite = db.query(models.OrderItem.dish_name, func.sum(models.OrderItem.quantity).label("count")).join(models.Order, models.Order.id == models.OrderItem.order_id).filter(models.Order.customer_id == customer_id).group_by(models.OrderItem.dish_name).order_by(func.sum(models.OrderItem.quantity).desc()).first()
    favorite_name = favorite[0] if favorite else None
    if meals or games:
        message = f"今天一起完成了 {int(meals)} 次用餐、{int(games)} 局游戏，默契值增加 {int(score_change)} 分。"
    else:
        message = "今天的共同记录还没有开始，慢慢选一件想一起做的小事吧。"
    recommendation = f"可以再点一次「{favorite_name}」，饭后下一局象棋。" if favorite_name else "先选一道都喜欢的菜，饭后下一局轻松的象棋。"
    return {"date": date.today(), "meals": int(meals), "games": int(games), "love_score_change": int(score_change), "message": message, "recommendation": recommendation, "favorite_dish": favorite_name}
