"""Production registry for every network-free LoveOS game AI."""

from ai.animal_ai import AnimalAI
from ai.dice_ai import DiceAI
from ai.flight_ai import FlightAI
from ai.gomoku_ai import GomokuAI
from ai.landlord_ai import LandlordAI
from ai.strategy import AIPersona, AIProvider, AIProviderRegistry
from games.chess.ai import ChessAI


AI_PROVIDERS = AIProviderRegistry(
    (
        AIProvider(
            game_type="dice",
            factory=DiceAI,
            personas=(
                AIPersona("random", "骰子新手", "random"),
                AIPersona("rule", "概率陪练", "probability"),
                AIPersona("strategy", "读心搭档", "probability_history_ready"),
            ),
        ),
        AIProvider(
            game_type="chinese_chess",
            aliases=("chess",),
            factory=lambda level: ChessAI(difficulty=level),
            personas=(
                AIPersona("random", "象棋练习生", "random"),
                AIPersona("rule", "象棋陪练官", "capture_check"),
            ),
        ),
        AIProvider(
            game_type="jungle",
            aliases=("animal",),
            factory=AnimalAI,
            personas=(
                AIPersona("random", "森林新手", "random"),
                AIPersona("rule", "森林向导", "rule"),
            ),
        ),
        AIProvider(
            game_type="landlord",
            factory=LandlordAI,
            personas=(
                AIPersona("random", "牌桌新手", "random"),
                AIPersona("rule", "牌桌搭档", "rule"),
            ),
        ),
        AIProvider(
            game_type="aeroplane",
            aliases=("flight",),
            factory=FlightAI,
            personas=(
                AIPersona("random", "飞行棋新手", "random"),
                AIPersona("rule", "飞行棋领航员", "rule"),
            ),
        ),
        AIProvider(
            game_type="gomoku",
            factory=GomokuAI,
            personas=(
                AIPersona("random", "五子棋新手", "random"),
                AIPersona("rule", "五子棋陪练", "rule"),
                AIPersona("strategy", "五子棋挑战者", "strategy"),
            ),
        ),
    )
)


__all__ = ["AI_PROVIDERS"]
