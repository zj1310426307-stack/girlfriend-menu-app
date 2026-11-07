"""Consensual undo/draw negotiation shared by turn-based game engines.

The negotiation is intentionally small and engine-agnostic:

- ``UNDO_OFFER`` / ``DRAW_OFFER`` put ``{"type": ..., "by": ...}`` on the
  authoritative state; only human players of a couple game may offer.
- ``UNDO_ACCEPT`` / ``DRAW_ACCEPT`` must come from the other player.
- ``UNDO_DECLINE`` / ``DRAW_DECLINE`` clear the pending offer (the offerer
  may use it to cancel their own request).
- Any successful MOVE clears the pending offer, so a stale request can never
  be accepted after the board has moved on.

Engines own the actual undo application because board shape, history depth
and capture semantics differ per game.
"""
from __future__ import annotations

from .engine import GameRuleError

NEGOTIATION_TYPES = ("undo", "draw")


def offer_negotiation(state: dict, player_id: str, kind: str, can_undo: bool = True) -> None:
    """Start an undo or draw offer from one human player of a couple game."""
    if kind not in NEGOTIATION_TYPES:
        raise GameRuleError("不支持的协商类型")
    if state.get("phase") != "playing":
        raise GameRuleError("当前对局阶段不能发起协商")
    if state.get("mode") == "ai":
        raise GameRuleError("人机模式不支持协商，可以新开一局调整难度")
    if player_id not in state.get("players", []):
        raise GameRuleError("玩家不属于这个房间")
    if kind == "undo" and not can_undo:
        raise GameRuleError("还没有可以悔的棋，先走一步再发起")
    state["negotiation"] = {"type": kind, "by": player_id}


def answer_negotiation(state: dict, player_id: str, expected: str, accept: bool) -> bool:
    """Resolve a pending offer; return True only when it was accepted."""
    negotiation = state.get("negotiation")
    if not negotiation or negotiation.get("type") != expected:
        raise GameRuleError("当前没有待回应的协商")
    if player_id not in state.get("players", []):
        raise GameRuleError("玩家不属于这个房间")
    if player_id != negotiation.get("by"):
        state["negotiation"] = None
        return accept
    # The offerer may only cancel (decline) their own request, never accept it.
    if accept:
        raise GameRuleError("只能由对方回应这个协商")
    state["negotiation"] = None
    return False
