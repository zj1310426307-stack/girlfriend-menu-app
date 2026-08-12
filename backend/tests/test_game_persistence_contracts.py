"""Phase 2C Round 1 contracts for durable game persistence boundaries."""

from datetime import datetime, timedelta, timezone
import re
from unittest.mock import Mock
import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from test_api import app

import models
from auth import hash_token
from core.game_room_lease import acquire_room_lease, release_room_lease
from database import Base, SessionLocal, engine
from services import game_persistence_service


@pytest.fixture(scope="module", autouse=True)
def service_schema():
    """Create the shared SQLite schema when this contract module runs alone."""
    Base.metadata.create_all(bind=engine)


def _player(marker: str, name: str) -> str:
    """Build a unique player identity for the shared test database."""
    return f"gf_phase2c_{name}_{marker}"


def test_room_catalog_creation_collision_status_and_missing_semantics(monkeypatch):
    """Catalogue validation and collision-safe room creation preserve exact errors."""
    marker = uuid.uuid4().hex[:10]
    with TestClient(app), SessionLocal() as db:
        games = game_persistence_service.list_games(db)
        assert [game.id for game in games] == sorted(game.id for game in games)
        with pytest.raises(HTTPException) as missing_game:
            game_persistence_service.create_game_room(
                db,
                f"missing_{marker}",
                _player(marker, "owner"),
            )
        assert missing_game.value.status_code == 404

        unavailable = models.Game(
            name=f"phase2c unavailable {marker}",
            icon="测",
            type=f"phase2c_unavailable_{marker}",
            status="coming_soon",
        )
        db.add(unavailable)
        db.commit()
        with pytest.raises(HTTPException) as unavailable_game:
            game_persistence_service.create_game_room(
                db,
                unavailable.type,
                _player(marker, "owner"),
            )
        assert unavailable_game.value.status_code == 409

        choices = iter("AAAAAABBBBBB")
        monkeypatch.setattr(
            game_persistence_service.secrets,
            "choice",
            lambda _alphabet: next(choices),
        )
        collision = models.GameRoom(
            room_code="AAAAAA",
            game_type="gomoku",
            creator=_player(marker, "collision"),
            status="finished",
            max_players=2,
        )
        db.add(collision)
        db.commit()
        room = game_persistence_service.create_game_room(
            db,
            "gomoku",
            _player(marker, "owner"),
        )
        assert room.room_code == "BBBBBB"
        assert re.fullmatch(r"[23456789A-HJ-NP-Z]{6}", room.room_code)
        assert game_persistence_service.get_game_room(db, room.room_code).id == room.id
        with pytest.raises(HTTPException) as missing_room:
            game_persistence_service.get_game_room(db, "ZZZZZZ")
        assert missing_room.value.status_code == 404


def test_player_join_idempotency_full_disconnect_and_commit_false(monkeypatch):
    """Seats, notification timing and caller-owned transactions remain compatible."""
    marker = uuid.uuid4().hex[:10]
    owner = _player(marker, "owner")
    guest = _player(marker, "guest")
    with TestClient(app), SessionLocal() as db:
        room = game_persistence_service.create_game_room(db, "gomoku", owner)
        first = game_persistence_service.join_game_room(db, room.room_code, owner)
        assert first.seat == 1
        assert game_persistence_service.join_game_room(
            db,
            room.room_code,
            owner,
        ).id == first.id

        # Suppress cross-domain notification commits while testing the gateway's
        # composed commit=False membership plus token transaction.
        monkeypatch.setattr(
            game_persistence_service,
            "_notify_joined_players",
            Mock(),
        )
        second = game_persistence_service.join_game_room(
            db,
            room.room_code,
            guest,
            commit=False,
        )
        token, expires_at = game_persistence_service.issue_room_session_token(
            db,
            second,
            commit=False,
        )
        assert token.startswith("gfr_")
        assert token != second.room_session_token_hash
        assert hash_token(token) == second.room_session_token_hash
        assert expires_at > datetime.now(timezone.utc)

        # A separate session cannot see the uncommitted seat or token.
        with SessionLocal() as observer:
            assert (
                observer.query(models.GamePlayer)
                .filter_by(room_id=room.id, player_id=guest)
                .first()
                is None
            )
        db.commit()
        with SessionLocal() as observer:
            persisted = (
                observer.query(models.GamePlayer)
                .filter_by(room_id=room.id, player_id=guest)
                .one()
            )
            assert hash_token(token) == persisted.room_session_token_hash
            assert observer.get(models.GameRoom, room.id).status == "playing"

        with pytest.raises(HTTPException) as full:
            game_persistence_service.join_game_room(
                db,
                room.room_code,
                _player(marker, "third"),
            )
        assert full.value.status_code == 409
        game_persistence_service.mark_game_player_disconnected(
            db,
            room.room_code,
            guest,
        )
        db.expire_all()
        disconnected = (
            db.query(models.GamePlayer)
            .filter_by(room_id=room.id, player_id=guest)
            .one()
        )
        assert disconnected.disconnected_at is not None
        assert disconnected.expires_at is not None


def test_room_session_reissue_rotates_raw_token_and_hash(monkeypatch):
    """A room-session reissue returns a new raw token and stores only its hash."""
    marker = uuid.uuid4().hex[:10]
    owner = _player(marker, "token")
    with TestClient(app), SessionLocal() as db:
        room = game_persistence_service.create_game_room(db, "gomoku", owner)
        player = game_persistence_service.join_game_room(db, room.room_code, owner)
        first, first_expiry = game_persistence_service.issue_room_session_token(db, player)
        first_hash = player.room_session_token_hash
        second, second_expiry = game_persistence_service.issue_room_session_token(db, player)
        assert first != second
        assert first_hash != player.room_session_token_hash
        assert hash_token(first) != player.room_session_token_hash
        assert hash_token(second) == player.room_session_token_hash
        assert first_expiry <= second_expiry


def test_finish_record_idempotency_winner_pending_visibility_and_lease_clear(monkeypatch):
    """One room/round record retains validation, score and pending settlement rules."""
    marker = uuid.uuid4().hex[:10]
    owner = _player(marker, "record_owner")
    guest = _player(marker, "record_guest")
    with TestClient(app), SessionLocal() as db:
        room = game_persistence_service.create_game_room(db, "gomoku", owner)
        game_persistence_service.join_game_room(db, room.room_code, owner)
        monkeypatch.setattr(
            game_persistence_service,
            "_notify_joined_players",
            Mock(),
        )
        game_persistence_service.join_game_room(db, room.room_code, guest)
        room.owner_instance_id = "phase2c-owner"
        room.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        db.commit()

        with pytest.raises(HTTPException) as bad_round:
            game_persistence_service.finish_game_room(
                db,
                room.room_code,
                owner,
                10,
                round_number=0,
            )
        assert bad_round.value.status_code == 422
        with pytest.raises(HTTPException) as invalid_winner:
            game_persistence_service.finish_game_room(
                db,
                room.room_code,
                "gf_not_a_member",
                10,
            )
        assert invalid_winner.value.status_code == 400

        record = game_persistence_service.finish_game_room(
            db,
            room.room_code,
            owner,
            42,
            {"_settlement": "pending", "move_count": 9},
            1,
        )
        retried = game_persistence_service.finish_game_room(
            db,
            room.room_code,
            owner,
            999,
            {"move_count": 99},
            1,
        )
        assert retried.id == record.id
        assert retried.duration == 42
        assert retried.settlement_status == "pending"
        assert retried.settlement_attempts == 0
        db.expire_all()
        persisted_room = game_persistence_service.get_game_room(db, room.room_code)
        assert persisted_room.status == "finished"
        assert persisted_room.owner_instance_id is None
        assert persisted_room.lease_expires_at is None
        winner = next(player for player in persisted_room.players if player.player_id == owner)
        assert winner.score == 1
        assert game_persistence_service.list_game_records(db, owner) == []

        record.result = {"_settlement": "complete", "move_count": 9}
        record.settlement_status = "complete"
        db.commit()
        visible = game_persistence_service.list_game_records(db, owner)
        assert [item.id for item in visible] == [record.id]

        ai_room = game_persistence_service.create_game_room(db, "gomoku", owner)
        game_persistence_service.join_game_room(db, ai_room.room_code, owner)
        ai_record = game_persistence_service.finish_game_room(
            db,
            ai_room.room_code,
            "ai_gomoku",
            8,
            {},
            1,
        )
        assert ai_record.winner == "ai_gomoku"


def test_postgres_style_room_lease_contract_remains_single_owner():
    """The existing database CAS lease keeps owner, epoch, takeover and release rules."""
    marker = uuid.uuid4().hex[:10]
    owner = _player(marker, "lease")
    with TestClient(app), SessionLocal() as db:
        room = game_persistence_service.create_game_room(db, "gomoku", owner)
        first = acquire_room_lease(db, room.room_code, "phase2c-instance-a", 30)
        assert first.acquired is True
        blocked = acquire_room_lease(db, room.room_code, "phase2c-instance-b", 30)
        assert blocked.acquired is False
        assert release_room_lease(db, room.room_code, "phase2c-instance-b") is False

        room = game_persistence_service.get_game_room(db, room.room_code)
        room.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        takeover = acquire_room_lease(db, room.room_code, "phase2c-instance-b", 30)
        assert takeover.acquired is True
        assert takeover.lease_epoch > first.lease_epoch
        assert release_room_lease(db, room.room_code, "phase2c-instance-a") is False
        assert release_room_lease(db, room.room_code, "phase2c-instance-b") is True
