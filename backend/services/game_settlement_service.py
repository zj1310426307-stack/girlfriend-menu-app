"""Retryable settlement orchestration for completed real-time game rounds.

The WebSocket gateway emits a completion event, while this service owns the
durable record and every existing post-game side effect.  The ordering here is
an externally significant recovery contract: maintenance jobs can continue a
``pending`` record after any process or database failure without inventing a
second round.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import couple_profile_service
import game_recovery_service
import notification_service
from core.telemetry import set_span_attribute, trace_span
from database import SessionLocal
from game_rewards import settle_game_rewards
from services import game_persistence_service


def persist_completed_game(event: dict, *, retry_count: int = 0):
    """Persist one real-time completion event using the deployed side-effect order.

    The record is committed as ``pending`` before rewards begin.  Replay,
    memory and notification writers already use durable source identifiers;
    repeated calls therefore return the same room/round record and repair only
    missing effects.
    """
    with trace_span(
        "game.settlement",
        {
            "game.type": event.get("game_type", "unknown"),
            "result": "error",
            "retry.count": retry_count,
        },
    ) as settlement_span:
        with SessionLocal() as db:
            with trace_span(
                "game.settlement.persist",
                {"settlement.stage": "persist", "result": "success"},
            ):
                result = dict(event.get("result") or {})
                result["_settlement"] = "pending"
                record = game_persistence_service.finish_game_room(
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

            with trace_span(
                "game.settlement.reward",
                {"settlement.stage": "reward", "result": "success"},
            ):
                settle_game_rewards(
                    db,
                    record,
                    event.get("players") or [],
                    event.get("winner_id"),
                )

            with trace_span(
                "game.settlement.replay",
                {"settlement.stage": "replay", "result": "success"},
            ):
                replay_state = result.get("final_state") or result
                game_recovery_service.save_replay(db, record, replay_state)

            with trace_span(
                "game.settlement.notification",
                {"settlement.stage": "notification", "result": "success"},
            ):
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
                    notification_service.create_notification_once(
                        db,
                        player_id,
                        "GAME_FINISHED",
                        "对局结果已经保存",
                        "战绩、积分和回放都可以在一起玩中查看。",
                        record.id,
                        trace_persist=True,
                    )

            with trace_span(
                "game.settlement.finalize",
                {"settlement.stage": "finalize", "result": "success"},
            ):
                record.result = {**(record.result or {}), "_settlement": "complete"}
                record.settlement_status = "complete"
                record.settlement_error = None
                record.settled_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(record)
            set_span_attribute(settlement_span, "result", "success")
            return record


async def persist_completed_game_with_retry(event: dict):
    """Run settlement off the event loop and retry one transient failure."""
    last_error = None
    for attempt in range(2):
        try:
            return await asyncio.to_thread(
                persist_completed_game,
                event,
                retry_count=attempt,
            )
        except Exception as error:  # Database drivers expose different transient errors.
            last_error = error
            if attempt == 0:
                await asyncio.sleep(0.2)
    raise last_error
