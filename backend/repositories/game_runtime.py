"""SQLAlchemy persistence primitives for durable game rooms and records.

This module deliberately excludes WebSockets, runtime managers, snapshots,
leases, rewards and settlement side effects. Callers choose transaction
boundaries explicitly where the existing gateway composes multiple writes.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, noload, selectinload

import models


def list_catalog(db: Session) -> list[models.Game]:
    """Return the persisted game catalogue in stable identifier order."""
    return db.query(models.Game).order_by(models.Game.id).all()


def find_game(db: Session, game_type: str) -> models.Game | None:
    """Find one game catalogue entry without applying HTTP semantics."""
    return db.query(models.Game).filter(models.Game.type == game_type).first()


def room_code_exists(db: Session, room_code: str) -> bool:
    """Check a generated room code without loading its relationships."""
    return bool(
        db.query(models.GameRoom.id)
        .filter(models.GameRoom.room_code == room_code)
        .first()
    )


def create_room(db: Session, room: models.GameRoom) -> models.GameRoom:
    """Commit and refresh a new room, rolling back a uniqueness race."""
    db.add(room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(room)
    return room


def find_room(db: Session, room_code: str) -> models.GameRoom | None:
    """Load room metadata with its model-configured response relationships."""
    return (
        db.query(models.GameRoom)
        .filter(models.GameRoom.room_code == room_code.strip().upper())
        .first()
    )


def find_room_runtime(db: Session, room_code: str) -> models.GameRoom | None:
    """Load only latency-sensitive room metadata with relationships disabled."""
    return (
        db.query(models.GameRoom)
        .options(noload("*"))
        .filter(models.GameRoom.room_code == room_code.strip().upper())
        .first()
    )


def save_room(db: Session, room: models.GameRoom) -> models.GameRoom:
    """Commit and refresh an already-mutated room row."""
    db.commit()
    db.refresh(room)
    return room


def find_room_with_players(db: Session, room_code: str) -> models.GameRoom | None:
    """Load one room and its ordered seats for membership orchestration."""
    return (
        db.query(models.GameRoom)
        .options(noload("*"), selectinload(models.GameRoom.players))
        .filter(models.GameRoom.room_code == room_code.strip().upper())
        .first()
    )


def find_player(
    db: Session,
    room_id: int,
    player_id: str,
) -> models.GamePlayer | None:
    """Find a player's durable seat inside one room."""
    return (
        db.query(models.GamePlayer)
        .filter(
            models.GamePlayer.room_id == room_id,
            models.GamePlayer.player_id == player_id,
        )
        .first()
    )


def list_players(db: Session, room_code: str) -> list[models.GamePlayer] | None:
    """Return ordered seats, or ``None`` when the room does not exist."""
    room_id = (
        db.query(models.GameRoom.id)
        .filter(models.GameRoom.room_code == room_code.strip().upper())
        .scalar()
    )
    if room_id is None:
        return None
    return (
        db.query(models.GamePlayer)
        .filter(models.GamePlayer.room_id == room_id)
        .order_by(models.GamePlayer.seat)
        .all()
    )


def save_player(
    db: Session,
    player: models.GamePlayer,
    *,
    commit: bool,
) -> models.GamePlayer:
    """Flush or commit one membership according to the caller-owned boundary."""
    db.add(player)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        raise
    if commit:
        db.refresh(player)
    return player


def save_player_activity(
    db: Session,
    player: models.GamePlayer,
    *,
    commit: bool,
) -> models.GamePlayer:
    """Persist an existing player's activity using an explicit commit policy."""
    if commit:
        db.commit()
    else:
        db.flush()
    return player


def save_room_session(
    db: Session,
    player: models.GamePlayer,
    *,
    commit: bool,
) -> None:
    """Flush or commit room-session fields already assigned by the service."""
    if commit:
        db.commit()
    else:
        db.flush()


def save_disconnect(db: Session) -> None:
    """Commit player disconnect and room activity mutations together."""
    db.commit()


def record_query(db: Session):
    """Build the shared record query with room and ordered player payload data."""
    return db.query(models.GameRecord).options(
        selectinload(models.GameRecord.room).selectinload(models.GameRoom.players)
    )


def find_round_record(
    db: Session,
    room_id: int,
    round_number: int,
) -> models.GameRecord | None:
    """Find the idempotency record for one durable room round."""
    return (
        record_query(db)
        .filter(
            models.GameRecord.room_id == room_id,
            models.GameRecord.round_number == round_number,
        )
        .first()
    )


def create_record(
    db: Session,
    record: models.GameRecord,
) -> models.GameRecord:
    """Commit a record plus mutated room/player rows, rolling back races."""
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    return record_query(db).filter(models.GameRecord.id == record.id).one()


def list_records_for_player(
    db: Session,
    customer_id: str,
    fetch_limit: int,
) -> list[models.GameRecord]:
    """Load newest records for one room member before visibility filtering."""
    return (
        record_query(db)
        .join(models.GameRoom, models.GameRecord.room_id == models.GameRoom.id)
        .join(models.GamePlayer, models.GamePlayer.room_id == models.GameRoom.id)
        .filter(models.GamePlayer.player_id == customer_id)
        .order_by(models.GameRecord.created_at.desc(), models.GameRecord.id.desc())
        .limit(fetch_limit)
        .all()
    )
