"""Database leases that prevent split-brain real-time room ownership."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import socket

from sqlalchemy import or_, update
from sqlalchemy.orm import Session, noload

import models


LEASE_SECONDS = max(15, int(os.getenv("GAME_ROOM_LEASE_SECONDS", "30")))
INSTANCE_ID = os.getenv("GAME_INSTANCE_ID", "").strip() or (
    f"{os.getenv('RENDER_INSTANCE_ID') or socket.gethostname()}:{os.getpid()}"
)


@dataclass(frozen=True)
class RoomLease:
    """Result returned to the WebSocket gateway after an ownership attempt."""

    acquired: bool
    owner_instance_id: str | None
    lease_epoch: int
    lease_expires_at: datetime | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def acquire_room_lease(
    db: Session,
    room_code: str,
    owner_instance_id: str = INSTANCE_ID,
    lease_seconds: int = LEASE_SECONDS,
) -> RoomLease:
    """Acquire or renew one active room lease with a database compare-and-set.

    Only the owning process may mutate the in-memory WebSocket engine. Another
    instance receives ``acquired=False`` and asks the client to reconnect; an
    expired owner can be replaced without manual cleanup.
    """
    normalized = room_code.strip().upper()
    now = _now()
    expires_at = now + timedelta(seconds=max(15, lease_seconds))
    room = (
        db.query(models.GameRoom)
        .options(noload("*"))
        .filter(models.GameRoom.room_code == normalized)
        .first()
    )
    if not room or room.status not in {"waiting", "playing"}:
        return RoomLease(False, getattr(room, "owner_instance_id", None), 0, None)

    if room.owner_instance_id == owner_instance_id:
        db.execute(
            update(models.GameRoom)
            .where(
                models.GameRoom.id == room.id,
                models.GameRoom.owner_instance_id == owner_instance_id,
            )
            .execution_options(synchronize_session=False)
            .values(lease_expires_at=expires_at)
        )
        db.commit()
    else:
        claimed = db.execute(
            update(models.GameRoom)
            .where(
                models.GameRoom.id == room.id,
                models.GameRoom.status.in_(("waiting", "playing")),
                or_(
                    models.GameRoom.owner_instance_id.is_(None),
                    models.GameRoom.lease_expires_at.is_(None),
                    models.GameRoom.lease_expires_at <= now,
                ),
            )
            .execution_options(synchronize_session=False)
            .values(
                owner_instance_id=owner_instance_id,
                lease_expires_at=expires_at,
                lease_epoch=models.GameRoom.lease_epoch + 1,
            )
        )
        db.commit()
        if claimed.rowcount != 1:
            db.expire_all()

    current = db.get(models.GameRoom, room.id)
    current_expiry = current.lease_expires_at if current else None
    if current_expiry and current_expiry.tzinfo is None:
        current_expiry = current_expiry.replace(tzinfo=timezone.utc)
    acquired = bool(
        current
        and current.owner_instance_id == owner_instance_id
        and current_expiry
        and current_expiry > now
    )
    return RoomLease(
        acquired,
        current.owner_instance_id if current else None,
        int(current.lease_epoch or 0) if current else 0,
        current_expiry,
    )


def renew_room_leases(
    db: Session,
    room_codes: list[str],
    owner_instance_id: str = INSTANCE_ID,
    lease_seconds: int = LEASE_SECONDS,
) -> int:
    """Heartbeat every locally active room without taking ownership from peers."""
    normalized = {code.strip().upper() for code in room_codes if code.strip()}
    if not normalized:
        return 0
    result = db.execute(
        update(models.GameRoom)
        .where(
            models.GameRoom.room_code.in_(normalized),
            models.GameRoom.owner_instance_id == owner_instance_id,
            models.GameRoom.status.in_(("waiting", "playing")),
        )
        .execution_options(synchronize_session=False)
        .values(lease_expires_at=_now() + timedelta(seconds=max(15, lease_seconds)))
    )
    db.commit()
    return int(result.rowcount or 0)


def release_room_lease(
    db: Session,
    room_code: str,
    owner_instance_id: str = INSTANCE_ID,
) -> bool:
    """Release ownership only when no local socket remains in the room."""
    result = db.execute(
        update(models.GameRoom)
        .where(
            models.GameRoom.room_code == room_code.strip().upper(),
            models.GameRoom.owner_instance_id == owner_instance_id,
        )
        .execution_options(synchronize_session=False)
        .values(owner_instance_id=None, lease_expires_at=None)
    )
    db.commit()
    return result.rowcount == 1
