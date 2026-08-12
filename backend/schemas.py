from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


OrderStatus = Literal["待接单", "已接单", "制作中", "已完成", "暂时做不了"]


class AdminLogin(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    invite_code: str = Field(min_length=1, max_length=100)


class AdminLoginOut(BaseModel):
    token: str
    expires_at: datetime


class CustomerSessionCreate(BaseModel):
    invite_code: str = Field(min_length=1, max_length=100)
    display_name: str = Field(default="女朋友", min_length=1, max_length=50)
    device_label: str | None = Field(default=None, max_length=100)


class CustomerLegacyClaim(CustomerSessionCreate):
    legacy_customer_id: str = Field(min_length=3, max_length=100)


class CustomerRecovery(CustomerLegacyClaim):
    """Recover an already claimed legacy identity or claim it for the first time."""


class CustomerSessionOut(BaseModel):
    customer_id: str
    customer_token: str
    display_name: str
    expires_at: datetime | None = None


class DiceRoomCreate(BaseModel):
    invite_code: str = Field(min_length=1, max_length=100)


class DiceRoomOut(BaseModel):
    room_code: str


GameStatus = Literal["available", "coming_soon", "maintenance"]
GameRoomStatus = Literal["waiting", "playing", "finished", "abandoned"]


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: str
    type: str
    status: GameStatus
    created_at: datetime


class GameRoomCreate(BaseModel):
    game_type: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    creator: str = Field(min_length=1, max_length=100)
    mode: Literal["couple", "ai"] = "couple"
    difficulty: Literal["random", "rule", "strategy"] = "rule"
    invite_code: str = Field(default="", max_length=100)


class GamePlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_id: str
    seat: int
    score: int
    joined_at: datetime


class GameRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_code: str
    game_type: str
    creator: str
    status: GameRoomStatus
    max_players: int
    created_at: datetime
    finished_at: datetime | None = None
    players: list[GamePlayerOut] = Field(default_factory=list)


class GameRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    room_code: str
    round_number: int
    game_type: str
    winner: str | None
    duration: int
    result: dict
    players: list[GamePlayerOut] = Field(default_factory=list)
    created_at: datetime


class GameStatsOut(BaseModel):
    total_games: int
    dice_games: int = 0
    gomoku_games: int
    flight_games: int
    landlord_games: int
    animal_games: int
    chess_games: int = 0
    today_games: int
    ai_games: int
    gomoku_win_rate: float
    player_win_rate: float
    most_played_game: str | None
    popular_games: list[dict]
    love_score_change: int
    interaction_count: int
    completed_tasks: int
    achievement_unlocks: int
    love_score_growth: list[dict]


AIDifficulty = Literal["random", "rule", "strategy"]


class GameSessionOut(BaseModel):
    """Viewer-filtered response shared by V2.5 turn-based games."""

    room_id: int
    room_code: str
    game_type: Literal["landlord", "jungle", "chinese_chess"]
    room_status: GameRoomStatus
    version: int
    state: dict
    updated_at: datetime


class LandlordRoomCreate(BaseModel):
    player_name: str = Field(default="男朋友", min_length=1, max_length=20)
    mode: Literal["couple", "ai"] = "couple"
    difficulty: AIDifficulty = "rule"
    invite_code: str = Field(default="", max_length=100)


class LandlordRoomJoin(BaseModel):
    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    player_name: str = Field(default="女朋友", min_length=1, max_length=20)
    invite_code: str = Field(default="", max_length=100)


class LandlordAction(BaseModel):
    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    action: Literal["BID", "PLAY", "PASS", "CHAT"]
    expected_version: int = Field(ge=1)
    client_action_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    bid: bool | None = None
    card_ids: list[str] = Field(default_factory=list, max_length=20)
    text: str | None = Field(default=None, max_length=80)


class AnimalRoomCreate(BaseModel):
    player_name: str = Field(default="男朋友", min_length=1, max_length=20)
    mode: Literal["couple", "ai"] = "couple"
    difficulty: AIDifficulty = "rule"
    invite_code: str = Field(default="", max_length=100)


class AnimalRoomJoin(BaseModel):
    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    player_name: str = Field(default="女朋友", min_length=1, max_length=20)
    invite_code: str = Field(default="", max_length=100)


class AnimalMove(BaseModel):
    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    action: Literal["MOVE", "RESIGN", "CHAT"] = "MOVE"
    expected_version: int = Field(ge=1)
    client_action_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    piece_id: str | None = Field(default=None, max_length=40)
    x: int | None = Field(default=None, ge=0, le=6)
    y: int | None = Field(default=None, ge=0, le=8)
    text: str | None = Field(default=None, max_length=80)


class ChessRoomCreate(BaseModel):
    """Create either a private couple room or server-owned AI training."""

    player_name: str = Field(default="男朋友", min_length=1, max_length=20)
    mode: Literal["couple", "ai"] = "couple"
    difficulty: AIDifficulty = "rule"
    invite_code: str = Field(default="", max_length=100)


class ChessRoomJoin(BaseModel):
    """Join the black seat of an existing couple room."""

    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    player_name: str = Field(default="女朋友", min_length=1, max_length=20)
    invite_code: str = Field(default="", max_length=100)


class ChessMoveAction(BaseModel):
    """Versioned Chinese-chess action using public board coordinates."""

    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    action: Literal["MOVE", "RESIGN", "CHAT"] = "MOVE"
    expected_version: int = Field(ge=1)
    client_action_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    from_pos: str | None = Field(default=None, pattern=r"^[a-iA-I](?:10|[1-9])$")
    to_pos: str | None = Field(default=None, pattern=r"^[a-iA-I](?:10|[1-9])$")
    text: str | None = Field(default=None, max_length=80)


class ChessMoveOut(BaseModel):
    """One persisted move returned in replay order."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    move_number: int
    player: str
    piece: str
    from_pos: str
    to_pos: str
    notation: str
    created_at: datetime


class ChessGameOut(BaseModel):
    """Chinese-chess match header with ownership-preserving player IDs."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    room_id: int
    round_number: int
    red_player: str
    black_player: str | None
    winner: str | None
    move_count: int
    duration: int
    created_at: datetime
    finished_at: datetime | None


class ChessHistoryOut(BaseModel):
    """Authorized replay payload."""

    game: ChessGameOut
    moves: list[ChessMoveOut]


class AIPlayerOut(BaseModel):
    """Public AI persona metadata without internal runtime state."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    game_type: str
    level: str
    name: str
    config: dict


class GameStatisticOut(BaseModel):
    """One game-type row for the current player."""

    game_type: str
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate: float


class RankingEntryOut(BaseModel):
    """Privacy-safe leaderboard entry."""

    rank: int
    display_name: str
    total_games: int
    wins: int
    win_rate: float


class GameRankingOut(BaseModel):
    """Current player's records and the scoped monthly leaderboard."""

    my_statistics: list[GameStatisticOut]
    monthly_ranking: list[RankingEntryOut]
    popular_games: list[dict]


class GameMemoryOut(BaseModel):
    """One private game-memory card."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    game_type: str
    event: str
    content: str
    related_id: int
    created_at: datetime


class DailyAISummaryOut(BaseModel):
    """Explainable daily companion summary generated from local records."""

    date: date
    meals: int
    games: int
    love_score_change: int
    message: str
    recommendation: str
    favorite_dish: str | None


class AIMoveRequest(BaseModel):
    """Request an AI turn against the server's current versioned session."""

    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    expected_version: int = Field(ge=1)


class AchievementOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    reward_score: int
    game_type: str | None
    metric: str
    threshold: int
    progress: int
    unlocked: bool
    unlocked_at: datetime | None


class LoveTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_record_id: int
    player_id: str
    title: str
    status: Literal["pending", "completed"]
    created_at: datetime
    completed_at: datetime | None


class FlightRoomCreate(BaseModel):
    player_name: str = Field(default="男朋友", min_length=1, max_length=20)
    mode: Literal["couple", "ai"] = "couple"
    difficulty: AIDifficulty = "rule"
    invite_code: str = Field(default="", max_length=100)


class FlightRoomJoin(BaseModel):
    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    player_name: str = Field(default="女朋友", min_length=1, max_length=20)
    invite_code: str = Field(default="", max_length=100)


class FlightAction(BaseModel):
    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    action: Literal["ROLL_DICE", "MOVE_PIECE", "COMPLETE_EVENT"]
    piece_index: int | None = Field(default=None, ge=0, le=3)
    expected_version: int | None = Field(default=None, ge=1)
    client_action_id: str | None = Field(default=None, min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class FlightStateOut(BaseModel):
    room_id: int
    room_code: str
    game_type: Literal["aeroplane"]
    room_status: GameRoomStatus
    state: dict
    updated_at: datetime


class GameEventLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    player_id: str
    content: str
    score: int
    status: Literal["pending", "completed"]
    created_at: datetime
    completed_at: datetime | None


class DailyTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    type: Literal["COMPLIMENT", "MEAL", "GAME", "REVIEW"]
    reward_score: int
    status: Literal["pending", "completed"]
    date: date
    created_at: datetime
    completed_at: datetime | None


class DailyTaskSummary(BaseModel):
    date: date
    completed_count: int
    total_count: int
    earned_score: int
    possible_score: int
    tasks: list[DailyTaskOut]
    recent_interactions: list[GameEventLogOut]


LoveScoreType = Literal[
    "ORDER_COMPLETE",
    "ORDER_REVIEW",
    "GAME_WIN",
    "GAME_PLAY",
    "COOK_COMPLETE",
    "SPECIAL_EVENT",
    "GAME_EVENT",
    "DAILY_TASK",
    "GAME_BONUS",
    "ACHIEVEMENT",
    "LOVE_TASK",
]


class LoveScoreCreate(BaseModel):
    type: LoveScoreType
    score: int = Field(ge=1, le=100)
    description: str = Field(min_length=1, max_length=300)
    related_id: int | None = Field(default=None, ge=1)


class LoveScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    score: int
    type: LoveScoreType
    description: str
    related_id: int | None
    time: datetime


class LoveScoreBreakdown(BaseModel):
    recent_interaction: int
    shared_experience: int
    satisfaction_feedback: int


class LoveScoreSummary(BaseModel):
    total: int
    level: str
    month_score: int
    points_total: int
    next_level_at: int | None
    progress: int
    month_meals: int
    month_games: int
    month_encouragement: int
    breakdown: LoveScoreBreakdown


class DishBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    category: str = Field(min_length=1, max_length=50)
    price: float = Field(ge=0)
    image_url: str = Field(default="", max_length=500)
    cook_time: int | None = Field(default=None, ge=0, le=1440)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    spicy_level: int | None = Field(default=0, ge=0, le=3)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value):
        if not value:
            return []
        normalized = []
        for raw_tag in value:
            tag = str(raw_tag).strip().lstrip("#")[:30]
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized


class DishCreate(DishBase):
    pass


class DishUpdate(DishBase):
    pass


class DishOut(DishBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class OrderItemCreate(BaseModel):
    dish_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(min_length=1, max_length=30)
    note: str = Field(default="", max_length=500)
    desired_time: str = Field(default="", max_length=50)
    desired_at: datetime | None = None
    customer_id: str | None = Field(default=None, max_length=100)
    source_order_id: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=12, max_length=100)


class OrderRepeatItem(BaseModel):
    dish_id: int
    name: str
    description: str = ""
    category: str = ""
    price: float
    image_url: str = ""
    quantity: int
    available: bool


class OrderRepeatDraft(BaseModel):
    source_order_id: int
    note: str = ""
    items: list[OrderRepeatItem]
    unavailable_names: list[str]


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dish_id: int
    dish_name: str
    price: float
    quantity: int


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    want_again: Literal["想吃", "一般", "暂时不想"]
    comment: str = Field(default="", max_length=500)


class ReviewOut(ReviewCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    note: str
    desired_time: str
    desired_at: datetime | None = None
    customer_id: str | None = None
    source_order_id: int | None = None
    status_updated_at: datetime | None = None
    created_at: datetime
    items: list[OrderItemOut]
    review: ReviewOut | None = None
    has_review: bool


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class AdminOrderPage(BaseModel):
    items: list[OrderOut]
    next_cursor: int | None = None
    total_estimate: int


UserRole = Literal["CUSTOMER", "ADMIN", "AI"]


class UserOut(BaseModel):
    """Unified identity returned without authentication secrets."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_code: str
    nickname: str
    avatar: str
    role: UserRole
    created_at: datetime


class UserUpdate(BaseModel):
    """Editable profile fields for the current device identity."""
    nickname: str = Field(min_length=1, max_length=50)
    avatar: str = Field(default="", max_length=500)


class NotificationOut(BaseModel):
    """One durable in-app notification."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    title: str
    content: str
    related_id: int | None
    is_read: bool
    created_at: datetime


MemoryType = Literal["FIRST_MEAL", "FIRST_COOK", "TRAVEL", "GAME", "ANNIVERSARY", "OTHER"]


class CoupleMemoryCreate(BaseModel):
    """Editable timeline entry payload."""
    type: MemoryType = "OTHER"
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(default="", max_length=2000)
    image_url: str = Field(default="", max_length=500)
    event_date: date
    source_type: str | None = Field(default=None, max_length=50)
    source_id: int | None = Field(default=None, ge=1)


class CoupleMemoryOut(CoupleMemoryCreate):
    """Timeline entry with durable identifiers."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CoupleDateCreate(BaseModel):
    """Anniversary payload supporting one-off or yearly recurrence."""
    title: str = Field(min_length=1, max_length=100)
    date: date
    repeat_type: Literal["NONE", "YEARLY"] = "YEARLY"
    reminder_days: int = Field(default=7, ge=0, le=60)


class CoupleDateOut(CoupleDateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CoupleProfileSummaryOut(BaseModel):
    days_together: int
    record_count: int
    month_meals: int
    month_games: int
    next_date_title: str | None
    next_date_days: int | None


class CoupleStatisticsOut(BaseModel):
    meals: int
    games: int
    interactions: int
    love_score: int
    favorite_dish: str | None
    favorite_game: str | None


class ReconnectTokenRequest(BaseModel):
    room_code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")


class ReconnectTokenOut(BaseModel):
    room_code: str
    game_type: str
    reconnect_token: str
    expires_at: datetime


class ReconnectRequest(BaseModel):
    reconnect_token: str = Field(min_length=20, max_length=200)


class ActiveGameOut(BaseModel):
    room_code: str
    game_type: str
    status: GameRoomStatus
    created_at: datetime
    cached: bool


class GameReplayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    game_record_id: int
    game_type: str
    moves: list
    final_state: dict
    created_at: datetime


class StatsSummary(BaseModel):
    total_orders: int
    completed_orders: int
    last_order_at: datetime | None


class DishStats(BaseModel):
    dish_id: int
    dish_name: str
    total_quantity: int
    last_ordered_at: datetime


class FavoriteRankingItem(BaseModel):
    dish_id: int
    name: str
    count: int
    rating: float | None = None
    repeat_count: int
    is_favorite: bool
    score: float
