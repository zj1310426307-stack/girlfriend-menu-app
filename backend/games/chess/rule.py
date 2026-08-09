"""Complete movement, check and legal-move validation for Chinese chess."""
from __future__ import annotations

from copy import deepcopy

from games.core.engine import GameRuleError

from .board import board_hash, crossed_river, in_palace, inside, opponent, piece_at


def _between(pieces: list[dict], x1: int, y1: int, x2: int, y2: int) -> list[dict]:
    """Return live pieces strictly between two orthogonally aligned squares."""
    if x1 != x2 and y1 != y2:
        return []
    dx = 0 if x1 == x2 else (1 if x2 > x1 else -1)
    dy = 0 if y1 == y2 else (1 if y2 > y1 else -1)
    x, y = x1 + dx, y1 + dy
    found = []
    while (x, y) != (x2, y2):
        occupant = piece_at(pieces, x, y)
        if occupant:
            found.append(occupant)
        x, y = x + dx, y + dy
    return found


def _shape_is_legal(pieces: list[dict], piece: dict, x: int, y: int, capture: bool) -> bool:
    """Validate one piece's movement shape and blocking rules."""
    dx, dy = x - piece["x"], y - piece["y"]
    adx, ady = abs(dx), abs(dy)
    kind, color = piece["kind"], piece["color"]
    if kind == "rook":
        return (dx == 0 or dy == 0) and not _between(pieces, piece["x"], piece["y"], x, y)
    if kind == "cannon":
        blockers = len(_between(pieces, piece["x"], piece["y"], x, y))
        return (dx == 0 or dy == 0) and blockers == (1 if capture else 0)
    if kind == "horse":
        if sorted((adx, ady)) != [1, 2]:
            return False
        leg = (piece["x"] + (dx // 2), piece["y"]) if adx == 2 else (piece["x"], piece["y"] + (dy // 2))
        return piece_at(pieces, *leg) is None
    if kind == "elephant":
        eye = (piece["x"] + dx // 2, piece["y"] + dy // 2)
        on_own_side = y >= 5 if color == "red" else y <= 4
        return adx == ady == 2 and on_own_side and piece_at(pieces, *eye) is None
    if kind == "guard":
        return adx == ady == 1 and in_palace(color, x, y)
    if kind == "king":
        return adx + ady == 1 and in_palace(color, x, y)
    if kind == "pawn":
        forward = -1 if color == "red" else 1
        return (dx == 0 and dy == forward) or (crossed_river(color, piece["y"]) and adx == 1 and dy == 0)
    return False


def kings_face(pieces: list[dict]) -> bool:
    """Return whether the two kings illegally face each other on one file."""
    kings = {piece["color"]: piece for piece in pieces if piece["alive"] and piece["kind"] == "king"}
    if len(kings) != 2 or kings["red"]["x"] != kings["black"]["x"]:
        return False
    return not _between(pieces, kings["red"]["x"], kings["red"]["y"], kings["black"]["x"], kings["black"]["y"])


def is_attacked(pieces: list[dict], x: int, y: int, by_color: str) -> bool:
    """Return whether a side attacks a coordinate, including flying generals."""
    target = piece_at(pieces, x, y)
    for piece in pieces:
        if not piece["alive"] or piece["color"] != by_color:
            continue
        if piece["kind"] == "king" and piece["x"] == x and target and target["kind"] == "king":
            if not _between(pieces, piece["x"], piece["y"], x, y):
                return True
        if _shape_is_legal(pieces, piece, x, y, bool(target)):
            return True
    return False


def in_check(pieces: list[dict], color: str) -> bool:
    """Return whether one side's king is currently under attack."""
    king = next((piece for piece in pieces if piece["alive"] and piece["color"] == color and piece["kind"] == "king"), None)
    return king is None or kings_face(pieces) or is_attacked(pieces, king["x"], king["y"], opponent(color))


def validate_move(pieces: list[dict], piece_id: str, target_x: int, target_y: int, color: str) -> dict:
    """Validate movement, capture and self-check, returning a simulated position."""
    if not inside(target_x, target_y):
        raise GameRuleError("目标位置超出棋盘")
    source = next((piece for piece in pieces if piece["alive"] and piece["id"] == piece_id), None)
    if not source or source["color"] != color:
        raise GameRuleError("请选择自己的棋子")
    target = piece_at(pieces, target_x, target_y)
    if target and target["color"] == color:
        raise GameRuleError("目标位置已有自己的棋子")
    if not _shape_is_legal(pieces, source, target_x, target_y, bool(target)):
        raise GameRuleError("该棋子不能这样走")
    simulated = deepcopy(pieces)
    moved = next(piece for piece in simulated if piece["id"] == piece_id)
    captured = piece_at(simulated, target_x, target_y)
    if captured:
        captured["alive"] = False
    moved["x"], moved["y"] = target_x, target_y
    if in_check(simulated, color):
        raise GameRuleError("这一步会让自己的将帅被将军")
    return {"piece": source, "target": target, "pieces": simulated}


def legal_moves(pieces: list[dict], color: str) -> list[dict]:
    """Enumerate all legal moves for AI choice and checkmate detection."""
    moves = []
    for piece in pieces:
        if not piece["alive"] or piece["color"] != color:
            continue
        for y in range(10):
            for x in range(9):
                try:
                    result = validate_move(pieces, piece["id"], x, y, color)
                except GameRuleError:
                    continue
                moves.append({
                    "piece_id": piece["id"],
                    "x": x,
                    "y": y,
                    "capture": result["target"]["kind"] if result["target"] else None,
                    "check": in_check(result["pieces"], opponent(color)),
                    "position_hash": board_hash(result["pieces"], opponent(color)),
                })
    return moves
