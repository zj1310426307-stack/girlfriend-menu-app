"""Single discoverable registry for every production LoveOS game."""

from games.animal.engine import AnimalGame
from games.chess.engine import ChessGame
from games.core.plugin import GamePlugin, GamePluginRegistry
from games.landlord.engine import LandlordGame


GAME_PLUGINS = GamePluginRegistry(
    (
        GamePlugin(
            game_type="dice",
            name="大话骰",
            icon="骰",
            max_players=2,
            realtime=True,
            replay=False,
            legacy_api_prefixes=("/api/games/dice", "/ws/games/dice"),
        ),
        GamePlugin(
            game_type="gomoku",
            name="五子棋",
            icon="棋",
            max_players=2,
            modes=("couple", "ai"),
            ai_levels=("random", "rule", "strategy"),
            legacy_api_prefixes=("/api/games/rooms", "/ws/game"),
        ),
        GamePlugin(
            game_type="aeroplane",
            name="飞行棋",
            icon="飞",
            max_players=2,
            aliases=("flight",),
            modes=("couple", "ai"),
            ai_levels=("random", "rule", "strategy"),
            legacy_api_prefixes=("/api/games/flight",),
        ),
        GamePlugin(
            game_type="landlord",
            name="斗地主",
            icon="牌",
            max_players=3,
            modes=("couple", "ai"),
            ai_levels=("random", "rule", "strategy"),
            engine_factory=LandlordGame,
            legacy_api_prefixes=("/api/games/landlord",),
        ),
        GamePlugin(
            game_type="jungle",
            name="斗兽棋",
            icon="兽",
            max_players=2,
            aliases=("animal",),
            modes=("couple", "ai"),
            ai_levels=("random", "rule", "strategy"),
            engine_factory=AnimalGame,
            legacy_api_prefixes=("/api/games/animal",),
        ),
        GamePlugin(
            game_type="chinese_chess",
            name="中国象棋",
            icon="象",
            max_players=2,
            aliases=("chess",),
            modes=("couple", "ai"),
            ai_levels=("random", "rule", "strategy"),
            engine_factory=ChessGame,
            legacy_api_prefixes=("/api/games/chess",),
        ),
    )
)


__all__ = ["GAME_PLUGINS"]
