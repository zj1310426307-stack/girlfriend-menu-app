"""Canonical Animal Chess terrain and board helpers."""


WIDTH = 7
HEIGHT = 9
RIVER = {(x, y) for x in (1, 2, 4, 5) for y in (3, 4, 5)}
DENS = {"blue": (3, 0), "red": (3, 8)}
TRAPS = {
    "blue": {(2, 0), (4, 0), (3, 1)},
    "red": {(2, 8), (4, 8), (3, 7)},
}


def inside(x: int, y: int) -> bool:
    """Return whether coordinates are on the 7×9 board."""
    return 0 <= x < WIDTH and 0 <= y < HEIGHT


def piece_at(pieces: list[dict], x: int, y: int) -> dict | None:
    """Find one living piece at coordinates."""
    return next((piece for piece in pieces if piece["alive"] and piece["x"] == x and piece["y"] == y), None)


def opponent(color: str) -> str:
    """Return the opposite side color."""
    return "red" if color == "blue" else "blue"
