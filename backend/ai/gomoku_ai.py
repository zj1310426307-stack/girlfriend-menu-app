"""Reserved Gomoku AI interface for future solo mode."""
from ai.base import AIPlayer


class GomokuAI(AIPlayer):
    """Choose an empty central cell; online Gomoku remains human-vs-human."""

    def choose_action(self, state: dict, player_id: str) -> dict:
        board = state.get("board") or []
        cells = [
            (abs(x - 7) + abs(y - 7), x, y)
            for y, row in enumerate(board)
            for x, value in enumerate(row)
            if value == 0
        ]
        if not cells:
            return {"action": "PASS"}
        _, x, y = min(cells)
        return {"action": "MOVE", "x": x, "y": y}
