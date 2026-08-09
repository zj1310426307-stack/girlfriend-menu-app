"""Coordinate parsing and compact move notation helpers."""

from games.core.engine import GameRuleError

from .board import inside


def parse_position(value: str) -> tuple[int, int]:
    """Parse the public a1-i10 coordinate format into zero-based x/y."""
    value = (value or "").strip().lower()
    if len(value) < 2 or value[0] < "a" or value[0] > "i" or not value[1:].isdigit():
        raise GameRuleError("坐标格式应为 a1 到 i10")
    x, y = ord(value[0]) - ord("a"), int(value[1:]) - 1
    if not inside(x, y):
        raise GameRuleError("坐标超出棋盘")
    return x, y


def format_position(x: int, y: int) -> str:
    """Convert a zero-based coordinate to a1-i10 notation."""
    return f"{chr(ord('a') + x)}{y + 1}"


def move_notation(piece: dict, from_xy: tuple[int, int], to_xy: tuple[int, int]) -> str:
    """Produce a readable, stable history label without claiming formal notation."""
    return f"{piece['label']} {format_position(*from_xy)}→{format_position(*to_xy)}"
