"""Board coordinates and shared Chinese-chess geometry helpers."""

WIDTH = 9
HEIGHT = 10


def inside(x: int, y: int) -> bool:
    """Return whether a coordinate belongs to the 9 x 10 board."""
    return 0 <= x < WIDTH and 0 <= y < HEIGHT


def opponent(color: str) -> str:
    """Return the opposite side color."""
    return "black" if color == "red" else "red"


def in_palace(color: str, x: int, y: int) -> bool:
    """Return whether a coordinate is inside one side's 3 x 3 palace."""
    return 3 <= x <= 5 and ((7 <= y <= 9) if color == "red" else (0 <= y <= 2))


def crossed_river(color: str, y: int) -> bool:
    """Return whether a pawn has crossed the river."""
    return y <= 4 if color == "red" else y >= 5


def piece_at(pieces: list[dict], x: int, y: int) -> dict | None:
    """Find the live piece occupying one coordinate."""
    return next((piece for piece in pieces if piece["alive"] and piece["x"] == x and piece["y"] == y), None)


def board_hash(pieces: list[dict], turn_color: str) -> str:
    """Create a stable repetition key from live pieces and the side to move."""
    values = sorted(
        f"{piece['color']}:{piece['kind']}:{piece['x']}:{piece['y']}"
        for piece in pieces
        if piece["alive"]
    )
    return f"{turn_color}|" + "|".join(values)
