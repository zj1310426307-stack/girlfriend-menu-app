from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Customer(Base):
    """Authenticated device identity; only a hash of the bearer token is stored."""

    __tablename__ = "customers"

    id = Column(String(100), primary_key=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(50), nullable=False, default="女朋友")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    legacy_customer_id = Column(String(100), nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=True, index=True)


class Dish(Base):
    __tablename__ = "dishes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    category = Column(String(50), nullable=False, index=True)
    price = Column(Float, nullable=False, default=0)
    image_url = Column(String(500), default="")
    cook_time = Column(Integer, nullable=True)
    difficulty = Column(Integer, nullable=True)
    spicy_level = Column(Integer, nullable=True, default=0)
    tags = Column(JSON, nullable=True, default=list)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(20), nullable=False, default="待接单", index=True)
    note = Column(Text, default="")
    desired_time = Column(String(50), default="")
    desired_at = Column(DateTime(timezone=True), nullable=True, index=True)
    customer_id = Column(String(100), nullable=True, index=True)
    source_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    idempotency_key = Column(String(100), nullable=True, unique=True, index=True)
    status_updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    review = relationship(
        "Review",
        back_populates="order",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    status_events = relationship(
        "OrderStatusEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderStatusEvent.id",
    )

    @property
    def has_review(self):
        return self.review is not None


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False, index=True)
    actor_type = Column(String(20), nullable=False, default="ADMIN")
    actor_id = Column(String(100), nullable=False, default="admin")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    order = relationship("Order", back_populates="status_events")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"), nullable=False)
    dish_name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    order = relationship("Order", back_populates="items")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    rating = Column(Integer, nullable=False)
    want_again = Column(String(20), nullable=False)
    comment = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    order = relationship("Order", back_populates="review")


class FavoriteDish(Base):
    __tablename__ = "favorite_dishes"
    __table_args__ = (
        UniqueConstraint("customer_id", "dish_id", name="uq_favorite_customer_dish"),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    dish_id = Column(Integer, ForeignKey("dishes.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    icon = Column(String(20), nullable=False, default="玩")
    type = Column(String(50), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="coming_soon", index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class GameRoom(Base):
    __tablename__ = "game_rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_code = Column(String(12), nullable=False, unique=True, index=True)
    game_type = Column(String(50), nullable=False, index=True)
    creator = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="waiting", index=True)
    max_players = Column(Integer, nullable=False, default=2)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True, index=True)
    last_activity_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    state_version = Column(Integer, nullable=False, default=1)
    owner_instance_id = Column(String(120), nullable=True, index=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    lease_epoch = Column(Integer, nullable=False, default=0)
    abandoned_at = Column(DateTime(timezone=True), nullable=True, index=True)

    players = relationship(
        "GamePlayer",
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="GamePlayer.seat",
    )
    records = relationship(
        "GameRecord",
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="GameRecord.round_number",
    )
    state = relationship(
        "GameState",
        back_populates="room",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    session = relationship(
        "GameSession",
        back_populates="room",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    event_logs = relationship(
        "GameEventLog",
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class GamePlayer(Base):
    __tablename__ = "game_players"
    __table_args__ = (
        UniqueConstraint("room_id", "player_id", name="uq_game_player_room_player"),
        UniqueConstraint("room_id", "seat", name="uq_game_player_room_seat"),
    )

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id = Column(String(100), nullable=False, index=True)
    seat = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False, default=0)
    joined_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    room_session_token_hash = Column(String(128), nullable=True, unique=True, index=True)
    last_activity_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    disconnected_at = Column(DateTime(timezone=True), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    room = relationship("GameRoom", back_populates="players")


class GameRecord(Base):
    __tablename__ = "game_records"
    __table_args__ = (
        UniqueConstraint("room_id", "round_number", name="uq_game_record_room_round"),
    )

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number = Column(Integer, nullable=False, default=1)
    game_type = Column(String(50), nullable=False, index=True)
    winner = Column(String(100), nullable=True, index=True)
    duration = Column(Integer, nullable=False, default=0)
    result = Column(JSON, nullable=False, default=dict)
    settlement_status = Column(String(20), nullable=False, default="pending", index=True)
    settlement_attempts = Column(Integer, nullable=False, default=0)
    settlement_error = Column(Text, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    room = relationship("GameRoom", back_populates="records")

    @property
    def room_code(self):
        return self.room.room_code

    @property
    def players(self):
        return self.room.players


class GameState(Base):
    __tablename__ = "game_states"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    game_type = Column(String(50), nullable=False, index=True)
    state = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    room = relationship("GameRoom", back_populates="state")


class GameSession(Base):
    """Versioned authoritative state used by V2.5 turn-based games."""

    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    game_type = Column(String(50), nullable=False, index=True)
    current_turn = Column(String(100), nullable=True, index=True)
    state = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)

    room = relationship("GameRoom", back_populates="session")


class GameAction(Base):
    """Idempotent action receipt committed with one authoritative state change."""

    __tablename__ = "game_actions"
    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "player_id",
            "client_action_id",
            name="uq_game_action_room_player_client",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id = Column(String(100), nullable=False, index=True)
    client_action_id = Column(String(80), nullable=False, index=True)
    action_type = Column(String(40), nullable=False, index=True)
    request_hash = Column(String(64), nullable=False)
    request_version = Column(Integer, nullable=False, default=0)
    response_version = Column(Integer, nullable=False, default=0)
    response_state = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class Achievement(Base):
    """Server-owned achievement definition and reward rule."""

    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    reward_score = Column(Integer, nullable=False, default=0)
    game_type = Column(String(50), nullable=True, index=True)
    metric = Column(String(50), nullable=False, default="plays")
    threshold = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class UserAchievement(Base):
    """Idempotent record that a device identity unlocked an achievement."""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "achievement_id",
            name="uq_user_achievement_customer_definition",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    achievement = relationship("Achievement", lazy="joined")


class LoveTask(Base):
    """A post-game couple interaction generated from one completed game."""

    __tablename__ = "love_tasks"
    __table_args__ = (
        UniqueConstraint(
            "game_record_id",
            "player_id",
            name="uq_love_task_record_player",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    game_record_id = Column(Integer, ForeignKey("game_records.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = Column(String(100), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)


class ChessGame(Base):
    """Durable Chinese-chess match header used for replay and statistics."""

    __tablename__ = "chess_games"
    __table_args__ = (UniqueConstraint("room_id", "round_number", name="uq_chess_game_room_round"),)

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False, default=1)
    red_player = Column(String(100), nullable=False, index=True)
    black_player = Column(String(100), nullable=True, index=True)
    winner = Column(String(100), nullable=True, index=True)
    move_count = Column(Integer, nullable=False, default=0)
    duration = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True, index=True)

    moves = relationship(
        "ChessMove",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ChessMove.move_number",
    )


class ChessMove(Base):
    """One immutable Chinese-chess move in replay order."""

    __tablename__ = "chess_moves"
    __table_args__ = (UniqueConstraint("game_id", "move_number", name="uq_chess_move_game_number"),)

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("chess_games.id", ondelete="CASCADE"), nullable=False, index=True)
    move_number = Column(Integer, nullable=False)
    player = Column(String(100), nullable=False, index=True)
    piece = Column(String(40), nullable=False)
    from_pos = Column(String(8), nullable=False)
    to_pos = Column(String(8), nullable=False)
    notation = Column(String(80), nullable=False, default="")
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    game = relationship("ChessGame", back_populates="moves")


class AIPlayer(Base):
    """Configurable AI persona catalog shared by all server-owned games."""

    __tablename__ = "ai_players"
    __table_args__ = (UniqueConstraint("game_type", "level", name="uq_ai_player_game_level"),)

    id = Column(Integer, primary_key=True, index=True)
    game_type = Column(String(50), nullable=False, index=True)
    level = Column(String(20), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    config = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class GameStatistic(Base):
    """Materialized per-player game totals rebuilt from durable records."""

    __tablename__ = "game_statistics"
    __table_args__ = (UniqueConstraint("player_id", "game_type", name="uq_game_stat_player_type"),)

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(String(100), nullable=False, index=True)
    game_type = Column(String(50), nullable=False, index=True)
    total_games = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    draws = Column(Integer, nullable=False, default=0)
    win_rate = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, index=True)


class GameMemory(Base):
    """Private, durable highlights shown only to the owning device identity."""

    __tablename__ = "game_memories"
    __table_args__ = (
        UniqueConstraint("customer_id", "game_type", "event", "related_id", name="uq_game_memory_event"),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    game_type = Column(String(50), nullable=False, index=True)
    event = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    related_id = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)


class User(Base):
    """Stable identity record that unifies customer, admin and AI codes."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_code = Column(String(100), nullable=False, unique=True, index=True)
    nickname = Column(String(50), nullable=False, default="用户")
    avatar = Column(String(500), nullable=False, default="")
    role = Column(String(20), nullable=False, default="CUSTOMER", index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)


class Notification(Base):
    """Durable in-app notification owned by one unified user."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False, default="")
    related_id = Column(Integer, nullable=True, index=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    user = relationship("User", lazy="joined")


class CoupleMemory(Base):
    """Editable couple timeline entry scoped to one user identity."""

    __tablename__ = "couple_memories"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source_type", "source_id", name="uq_couple_memory_source"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False, default="")
    image_url = Column(String(500), nullable=False, default="")
    event_date = Column(Date, nullable=False, index=True)
    source_type = Column(String(50), nullable=True, index=True)
    source_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)


class CoupleDate(Base):
    """One-off or annually recurring private anniversary reminder."""

    __tablename__ = "couple_dates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    date = Column(Date, nullable=False, index=True)
    repeat_type = Column(String(20), nullable=False, default="YEARLY")
    reminder_days = Column(Integer, nullable=False, default=7)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)


class GameReconnectToken(Base):
    """Hashed, expiring room-recovery credential for one human member."""

    __tablename__ = "game_reconnect_tokens"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_reconnect_room_user"),)

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)


class GameReplay(Base):
    """Generic immutable replay snapshot attached to one completed record."""

    __tablename__ = "game_replays"

    id = Column(Integer, primary_key=True, index=True)
    game_record_id = Column(Integer, ForeignKey("game_records.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    game_type = Column(String(50), nullable=False, index=True)
    moves = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    final_state = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)


class GameEvent(Base):
    __tablename__ = "game_events"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    score = Column(Integer, nullable=False, default=3)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    logs = relationship("GameEventLog", back_populates="event")


class GameEventLog(Base):
    __tablename__ = "game_event_logs"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("game_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(Integer, ForeignKey("game_events.id"), nullable=False, index=True)
    player_id = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    score = Column(Integer, nullable=False, default=3)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)

    room = relationship("GameRoom", back_populates="event_logs")
    event = relationship("GameEvent", back_populates="logs")


class DailyTask(Base):
    __tablename__ = "daily_tasks"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "date",
            "type",
            name="uq_daily_task_customer_date_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    type = Column(String(50), nullable=False, index=True)
    reward_score = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="pending", index=True)
    date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    completed_at = Column(DateTime, nullable=True, index=True)


class LoveScore(Base):
    __tablename__ = "love_scores"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "type",
            "related_id",
            name="uq_love_score_source",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    type = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    related_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    @property
    def time(self):
        return self.created_at
