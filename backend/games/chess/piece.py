"""Chinese-chess piece definitions and initial placement."""

PIECE_LABELS = {
    "red": {"king": "帅", "guard": "仕", "elephant": "相", "horse": "马", "rook": "车", "cannon": "炮", "pawn": "兵"},
    "black": {"king": "将", "guard": "士", "elephant": "象", "horse": "马", "rook": "车", "cannon": "炮", "pawn": "卒"},
}

PIECE_VALUES = {"king": 10000, "rook": 900, "cannon": 450, "horse": 400, "elephant": 200, "guard": 200, "pawn": 100}


def _piece(color: str, kind: str, index: int, x: int, y: int) -> dict:
    """Build one JSON-safe piece with a stable identifier."""
    return {
        "id": f"{color}_{kind}_{index}",
        "color": color,
        "kind": kind,
        "label": PIECE_LABELS[color][kind],
        "x": x,
        "y": y,
        "alive": True,
    }


def initial_pieces() -> list[dict]:
    """Return the standard 32-piece initial position."""
    pieces: list[dict] = []
    back = ("rook", "horse", "elephant", "guard", "king", "guard", "elephant", "horse", "rook")
    for color, back_y, cannon_y, pawn_y in (("black", 0, 2, 3), ("red", 9, 7, 6)):
        counts: dict[str, int] = {}
        for x, kind in enumerate(back):
            index = counts.get(kind, 0)
            pieces.append(_piece(color, kind, index, x, back_y))
            counts[kind] = index + 1
        pieces.extend((_piece(color, "cannon", 0, 1, cannon_y), _piece(color, "cannon", 1, 7, cannon_y)))
        pieces.extend(_piece(color, "pawn", index, x, pawn_y) for index, x in enumerate((0, 2, 4, 6, 8)))
    return pieces
