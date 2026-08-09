"""Bounded chat state helper with no persistence dependencies."""
from datetime import datetime

from .engine import GameRuleError


def append_chat(state: dict, player_id: str, text: str) -> dict:
    """Append one sanitized message while bounding serialized state size."""
    clean = " ".join(str(text or "").strip().split())[:80]
    if not clean:
        raise GameRuleError("聊天内容不能为空")
    messages = list(state.get("messages") or [])[-29:]
    messages.append({"player_id": player_id, "text": clean, "time": datetime.now().isoformat()})
    state["messages"] = messages
    return state
