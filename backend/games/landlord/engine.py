"""Pure authoritative state machine for V2.5 landlord."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from games.core.engine import GameEngine, GameRuleError
from games.core.chat import append_chat

from .card import sort_cards
from .dealer import deal
from .rule import beats, classify


AI_ID = "ai_landlord"
AI_ID_2 = "ai_landlord_b"


class LandlordGame(GameEngine):
    """Manage bidding, card ownership, turn order and win detection."""

    def __init__(self, state: dict):
        self.state = deepcopy(state)

    @classmethod
    def waiting(
        cls,
        human_ids: list[str],
        names: dict[str, str] | None = None,
        difficulty: str = "rule",
        mode: str = "couple",
    ):
        """Create a waiting or freshly dealt game from persisted human seats."""
        ai_ids = [AI_ID, AI_ID_2] if mode == "ai" else [AI_ID]
        players = [*human_ids, *ai_ids]
        state = {
            "phase": "waiting",
            "players": players,
            "human_ids": list(human_ids),
            "names": {
                **(names or {}),
                AI_ID: "豆豆 AI",
                **({AI_ID_2: "小满 AI"} if mode == "ai" else {}),
            },
            "mode": mode,
            "difficulty": difficulty,
            "hands": {player_id: [] for player_id in players},
            "bottom_cards": [],
            "bids": [],
            "landlord_id": None,
            "turn_id": human_ids[0] if human_ids else None,
            "last_play": None,
            "pass_count": 0,
            "winner_id": None,
            "messages": [],
            "round": 1,
            "started_at": None,
        }
        game = cls(state)
        if len(players) == 3 and (mode == "ai" or len(human_ids) == 2):
            game.start()
        return game

    def start(self) -> dict:
        """Deal only after the logical three seats are present."""
        if len(self.state["players"]) != 3:
            raise GameRuleError("还需要一位玩家加入")
        hands, bottom = deal()
        for player_id, hand in zip(self.state["players"], hands):
            self.state["hands"][player_id] = hand
        self.state.update(
            phase="bidding",
            bottom_cards=bottom,
            turn_id=self.state["players"][0],
            started_at=datetime.now().isoformat(),
        )
        return self.serialize()

    def _next(self, player_id: str) -> str:
        players = self.state["players"]
        return players[(players.index(player_id) + 1) % len(players)]

    def bid(self, player_id: str, value: bool) -> dict:
        """Record each player's one bidding decision and start card play."""
        if self.state["phase"] != "bidding" or self.state["turn_id"] != player_id:
            raise GameRuleError("现在不是你的叫地主回合")
        if any(item["player_id"] == player_id for item in self.state["bids"]):
            raise GameRuleError("你已经叫过地主")
        self.state["bids"].append({"player_id": player_id, "bid": bool(value)})
        if len(self.state["bids"]) < len(self.state["players"]):
            self.state["turn_id"] = self._next(player_id)
            return self.serialize()
        landlord = next((item["player_id"] for item in self.state["bids"] if item["bid"]), AI_ID)
        self.state["landlord_id"] = landlord
        self.state["hands"][landlord] = sort_cards(
            self.state["hands"][landlord] + self.state["bottom_cards"]
        )
        self.state["phase"] = "playing"
        self.state["turn_id"] = landlord
        return self.serialize()

    def play(self, player_id: str, card_ids: list[str]) -> dict:
        """Validate ownership and combination, then remove the cards atomically."""
        if self.state["phase"] != "playing" or self.state["turn_id"] != player_id:
            raise GameRuleError("现在不是你的出牌回合")
        unique_ids = list(dict.fromkeys(card_ids or []))
        if len(unique_ids) != len(card_ids or []):
            raise GameRuleError("不能重复选择同一张牌")
        hand = self.state["hands"][player_id]
        selected = [card for card in hand if card["id"] in unique_ids]
        if len(selected) != len(unique_ids):
            raise GameRuleError("所选牌不在你的手牌中")
        combo = classify(selected)
        previous = self.state.get("last_play")
        if previous and previous["player_id"] != player_id and not beats(combo, previous["combo"]):
            raise GameRuleError("这手牌压不过当前牌型")
        selected_set = set(unique_ids)
        self.state["hands"][player_id] = [card for card in hand if card["id"] not in selected_set]
        self.state["last_play"] = {
            "player_id": player_id,
            "cards": sort_cards(selected),
            "combo": combo,
        }
        self.state["pass_count"] = 0
        if not self.state["hands"][player_id]:
            self.state.update(phase="finished", winner_id=player_id, turn_id=None)
        else:
            self.state["turn_id"] = self._next(player_id)
        return self.serialize()

    def pass_turn(self, player_id: str) -> dict:
        """Pass only when another player owns the current table play."""
        if self.state["phase"] != "playing" or self.state["turn_id"] != player_id:
            raise GameRuleError("现在不是你的回合")
        previous = self.state.get("last_play")
        if not previous or previous["player_id"] == player_id:
            raise GameRuleError("你是本轮领出玩家，不能不出")
        self.state["pass_count"] += 1
        if self.state["pass_count"] >= 2:
            leader = previous["player_id"]
            self.state["last_play"] = None
            self.state["pass_count"] = 0
            self.state["turn_id"] = leader
        else:
            self.state["turn_id"] = self._next(player_id)
        return self.serialize()

    def apply(self, player_id: str, action: str, data: dict[str, Any] | None = None) -> dict:
        """Dispatch one supported action through the pure state machine."""
        data = data or {}
        if player_id not in self.state["players"]:
            raise GameRuleError("玩家不属于这个房间")
        if action == "BID":
            return self.bid(player_id, bool(data.get("bid")))
        if action == "PLAY":
            return self.play(player_id, list(data.get("card_ids") or []))
        if action == "PASS":
            return self.pass_turn(player_id)
        if action == "CHAT":
            append_chat(self.state, player_id, data.get("text", ""))
            return self.serialize()
        raise GameRuleError("不支持的斗地主动作")

    def serialize(self) -> dict:
        """Return a deep copy so callers cannot mutate the engine accidentally."""
        return deepcopy(self.state)

    def public_state(self, viewer_id: str) -> dict:
        """Hide every other hand while retaining counts and revealed table cards."""
        state = self.serialize()
        state["hand_counts"] = {key: len(value) for key, value in state["hands"].items()}
        state["my_hand"] = state["hands"].get(viewer_id, [])
        state.pop("hands", None)
        if state["phase"] == "bidding":
            state["bottom_cards"] = []
        return state
