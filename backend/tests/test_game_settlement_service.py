"""Crash-window contracts for real-time game settlement extraction."""

import uuid

from fastapi.testclient import TestClient
import pytest

import game_maintenance
import models
from database import SessionLocal
from services import game_persistence_service, game_settlement_service
from test_api import app


def _event() -> dict:
    """Create one completed room and its replayable WebSocket event."""
    winner = f"gf_settle_win_{uuid.uuid4().hex[:8]}"
    loser = f"gf_settle_lose_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        room = game_persistence_service.create_game_room(db, "gomoku", winner)
        game_persistence_service.join_game_room(db, room.room_code, winner)
        game_persistence_service.join_game_room(db, room.room_code, loser)
        room_code = room.room_code
    state = {
        "phase": "finished",
        "winner_id": winner,
        "round": 1,
        "board": [],
        "move_count": 9,
    }
    return {
        "room_code": room_code,
        "game_type": "gomoku",
        "round_number": 1,
        "players": [winner, loser],
        "winner_id": winner,
        "duration": 12,
        "result": {"final_state": state, "move_count": 9},
    }


def test_crash_after_pending_record_is_reconciled_without_double_reward(monkeypatch):
    """A replay-stage crash leaves pending data that maintenance repairs once."""
    event = _event()
    real_save_replay = game_settlement_service.game_recovery_service.save_replay
    calls = {"count": 0}

    def fail_first_replay(db, record, state):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated replay outage")
        return real_save_replay(db, record, state)

    monkeypatch.setattr(
        game_settlement_service.game_recovery_service,
        "save_replay",
        fail_first_replay,
    )
    with TestClient(app):
        with pytest.raises(RuntimeError, match="replay outage"):
            game_settlement_service.persist_completed_game(event)

        with SessionLocal() as db:
            room = game_persistence_service.get_game_room(db, event["room_code"])
            record = (
                db.query(models.GameRecord)
                .filter(models.GameRecord.room_id == room.id)
                .one()
            )
            assert record.settlement_status == "pending"
            assert (record.result or {})["_settlement"] == "pending"
            before = db.query(models.LoveScore).filter(
                models.LoveScore.related_id == record.id,
                models.LoveScore.type.in_(("GAME_PLAY", "GAME_WIN", "SPECIAL_EVENT")),
            ).count()
            repaired = game_maintenance.reconcile_game_settlements(db)
            assert repaired["repaired"] >= 1
            db.refresh(record)
            assert record.settlement_status == "complete"
            after = db.query(models.LoveScore).filter(
                models.LoveScore.related_id == record.id,
                models.LoveScore.type.in_(("GAME_PLAY", "GAME_WIN", "SPECIAL_EVENT")),
            ).count()
            assert after == before
            replay_count = db.query(models.GameReplay).filter(
                models.GameReplay.game_record_id == record.id
            ).count()
            assert replay_count == 1

            game_maintenance.reconcile_game_settlements(db)
            assert db.query(models.LoveScore).filter(
                models.LoveScore.related_id == record.id,
                models.LoveScore.type.in_(("GAME_PLAY", "GAME_WIN", "SPECIAL_EVENT")),
            ).count() == after
            assert db.query(models.GameReplay).filter(
                models.GameReplay.game_record_id == record.id
            ).count() == 1


def test_repeated_completed_event_repairs_missing_replay_without_duplicate_rewards():
    """Re-delivery of one room/round event is fully idempotent."""
    event = _event()
    with TestClient(app):
        first = game_settlement_service.persist_completed_game(event)
        record_id = first.id
        with SessionLocal() as db:
            db.query(models.GameReplay).filter(
                models.GameReplay.game_record_id == record_id
            ).delete()
            db.commit()
            score_count = db.query(models.LoveScore).filter(
                models.LoveScore.related_id == record_id,
                models.LoveScore.type.in_(("GAME_PLAY", "GAME_WIN", "SPECIAL_EVENT")),
            ).count()

        second = game_settlement_service.persist_completed_game(event)
        assert second.id == record_id
        with SessionLocal() as db:
            assert db.query(models.GameReplay).filter(
                models.GameReplay.game_record_id == record_id
            ).count() == 1
            assert db.query(models.LoveScore).filter(
                models.LoveScore.related_id == record_id,
                models.LoveScore.type.in_(("GAME_PLAY", "GAME_WIN", "SPECIAL_EVENT")),
            ).count() == score_count
            assert db.query(models.Notification).filter(
                models.Notification.type == "GAME_FINISHED",
                models.Notification.related_id == record_id,
            ).count() == 2
