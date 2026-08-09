"""Animal Chess piece ranks and initial 7x9 placement."""


RANKS = {
    "rat": 1,
    "cat": 2,
    "dog": 3,
    "wolf": 4,
    "leopard": 5,
    "tiger": 6,
    "lion": 7,
    "elephant": 8,
}
LABELS = {
    "rat": "鼠",
    "cat": "猫",
    "dog": "狗",
    "wolf": "狼",
    "leopard": "豹",
    "tiger": "虎",
    "lion": "狮",
    "elephant": "象",
}


INITIAL = {
    "blue": {
        "lion": (0, 0), "tiger": (6, 0), "dog": (1, 1), "cat": (5, 1),
        "rat": (0, 2), "leopard": (2, 2), "wolf": (4, 2), "elephant": (6, 2),
    },
    "red": {
        "tiger": (0, 8), "lion": (6, 8), "cat": (1, 7), "dog": (5, 7),
        "elephant": (0, 6), "wolf": (2, 6), "leopard": (4, 6), "rat": (6, 6),
    },
}


def initial_pieces() -> list[dict]:
    """Return all sixteen pieces with stable ids and ranks."""
    return [
        {
            "id": f"{color}_{kind}",
            "color": color,
            "kind": kind,
            "label": LABELS[kind],
            "rank": RANKS[kind],
            "x": position[0],
            "y": position[1],
            "alive": True,
        }
        for color, pieces in INITIAL.items()
        for kind, position in pieces.items()
    ]
