"""Legal movement, river jumps and capture rules for Animal Chess."""
from __future__ import annotations

from games.core.engine import GameRuleError

from .board import DENS, RIVER, TRAPS, inside, piece_at


def _jump_target(piece: dict, dx: int, dy: int, pieces: list[dict]) -> tuple[int, int] | None:
    """Resolve a lion/tiger river jump unless a rat blocks the water lane."""
    x, y = piece["x"] + dx, piece["y"] + dy
    if (x, y) not in RIVER or piece["kind"] not in {"lion", "tiger"}:
        return None
    while (x, y) in RIVER:
        blocker = piece_at(pieces, x, y)
        if blocker and blocker["kind"] == "rat":
            raise GameRuleError("河里有老鼠挡住，狮虎不能跳河")
        x, y = x + dx, y + dy
    return (x, y)


def can_capture(attacker: dict, defender: dict) -> bool:
    """Apply trap, water and rat-elephant exceptions before rank comparison."""
    attack_water = (attacker["x"], attacker["y"]) in RIVER
    defend_water = (defender["x"], defender["y"]) in RIVER
    if attack_water != defend_water:
        return False
    if (defender["x"], defender["y"]) in TRAPS[attacker["color"]]:
        return True
    if attacker["kind"] == "rat" and defender["kind"] == "elephant":
        return True
    if attacker["kind"] == "elephant" and defender["kind"] == "rat":
        return False
    return attacker["rank"] >= defender["rank"]


def validate_move(pieces: list[dict], piece_id: str, target_x: int, target_y: int, color: str) -> dict:
    """Validate one move and return the destination piece if it will be captured."""
    piece = next((item for item in pieces if item["id"] == piece_id and item["alive"]), None)
    if not piece or piece["color"] != color:
        raise GameRuleError("请选择自己的棋子")
    if not inside(target_x, target_y):
        raise GameRuleError("目标位置超出棋盘")
    dx, dy = target_x - piece["x"], target_y - piece["y"]
    if abs(dx) + abs(dy) != 1:
        raise GameRuleError("每回合只能上下左右移动一格")
    jump = _jump_target(piece, dx, dy, pieces)
    if jump:
        target_x, target_y = jump
    if (target_x, target_y) == DENS[color]:
        raise GameRuleError("不能进入自己的兽穴")
    if (target_x, target_y) in RIVER and piece["kind"] != "rat":
        raise GameRuleError("只有老鼠可以下水")
    target = piece_at(pieces, target_x, target_y)
    if target and target["color"] == color:
        raise GameRuleError("目标格已有自己的棋子")
    if target and not can_capture(piece, target):
        raise GameRuleError("当前棋子不能吃掉目标")
    return {"piece": piece, "target": target, "x": target_x, "y": target_y}


def legal_moves(pieces: list[dict], color: str) -> list[dict]:
    """Enumerate legal moves for AI and no-move detection."""
    moves = []
    for piece in pieces:
        if not piece["alive"] or piece["color"] != color:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            try:
                result = validate_move(pieces, piece["id"], piece["x"] + dx, piece["y"] + dy, color)
            except GameRuleError:
                continue
            moves.append(
                {
                    "piece_id": piece["id"],
                    "x": result["x"],
                    "y": result["y"],
                    "capture": bool(result["target"]),
                }
            )
    return moves
