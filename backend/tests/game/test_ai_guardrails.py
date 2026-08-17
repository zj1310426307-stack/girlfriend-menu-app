"""Game Center V3 AI legality, stability and latency evidence."""

from __future__ import annotations

import time

from ai.dice_ai import DiceAI
from ai.registry import AI_PROVIDERS
from dice_rules import is_higher_bid


def _gomoku_state() -> dict:
    board = [[0 for _ in range(15)] for _ in range(15)]
    board[7][4:8] = [2, 2, 2, 2]
    return {
        "board": board,
        "players": [
            {"id": "human", "color": "black"},
            {"id": "ai_gomoku", "color": "white"},
        ],
    }


def test_gomoku_strategy_is_stable_and_uses_its_transposition_cache() -> None:
    """Return the same immediate win and cache the repeated board decision."""
    provider = AI_PROVIDERS.resolve("gomoku")
    strategy = provider.create("strategy")
    first = strategy.choose_action(_gomoku_state(), "ai_gomoku")
    second = strategy.choose_action(_gomoku_state(), "ai_gomoku")
    assert first == second
    assert first["action"] == "MOVE"
    assert first["y"] == 7
    assert len(strategy._action_cache) == 1


def test_dice_probability_ai_returns_a_legal_action_under_budget() -> None:
    """Use private dice and history without reading hidden opponent dice."""
    state = {
        "players": [{"id": "human"}, {"id": "ai_dice"}],
        "own_dice": [1, 2, 2, 4, 6],
        "current_bid": {"quantity": 3, "face": 2, "bidder_id": "human"},
        "opponent_history": [
            {"bid_succeeded": False},
            {"bid_succeeded": True},
        ],
    }
    started = time.perf_counter()
    action = DiceAI("strategy").choose_action(state, "ai_dice")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert elapsed_ms < 50
    assert action["action"] in {"BID", "CHALLENGE"}
    if action["action"] == "BID":
        assert is_higher_bid(state["current_bid"], action)


def test_registry_reports_latency_budget_without_mutating_actions() -> None:
    """Attach performance evidence to the shared AI result envelope."""
    decision = AI_PROVIDERS.choose_action(
        "gomoku",
        _gomoku_state(),
        "ai_gomoku",
        "strategy",
    )
    assert decision.action["action"] == "MOVE"
    assert decision.budget_ms == 100
    assert decision.within_budget
