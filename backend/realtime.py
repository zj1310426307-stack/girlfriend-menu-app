import asyncio
import secrets
from collections import OrderedDict

from fastapi import WebSocket


ROOM_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
DICE_PER_PLAYER = 5


def is_higher_bid(current_bid, next_bid):
    if not next_bid:
        return False
    quantity = next_bid.get("quantity", 0)
    face = next_bid.get("face", 0)
    if quantity < 1 or face < 1 or face > 6:
        return False
    if not current_bid:
        return True
    return quantity > current_bid["quantity"] or (
        quantity == current_bid["quantity"] and face > current_bid["face"]
    )


class OrderEventHub:
    def __init__(self):
        self.connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def add(self, websocket: WebSocket):
        async with self.lock:
            self.connections.add(websocket)

    async def remove(self, websocket: WebSocket):
        async with self.lock:
            self.connections.discard(websocket)

    async def broadcast(self, event_type: str, order_id: int):
        payload = {"type": event_type, "order_id": order_id}
        async with self.lock:
            connections = list(self.connections)
        stale = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        if stale:
            async with self.lock:
                for websocket in stale:
                    self.connections.discard(websocket)


class DiceRoomManager:
    def __init__(self):
        self.rooms = {}
        self.lock = asyncio.Lock()

    async def create_room(self):
        async with self.lock:
            while True:
                room_code = "".join(secrets.choice(ROOM_ALPHABET) for _ in range(6))
                if room_code not in self.rooms:
                    self.rooms[room_code] = self._new_room(room_code)
                    return room_code

    @staticmethod
    def _new_room(room_code):
        return {
            "room_code": room_code,
            "players": OrderedDict(),
            "dice": {},
            "phase": "waiting",
            "turn_id": None,
            "current_bid": None,
            "outcome": None,
            "rematch_ready": set(),
            "round": 0,
        }

    async def join(self, room_code, player_id, player_name, websocket):
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return False, "房间不存在或已经失效"
            if player_id not in room["players"] and len(room["players"]) >= 2:
                return False, "房间已经满了"
            room["players"][player_id] = {
                "id": player_id,
                "name": player_name[:20] or "玩家",
                "socket": websocket,
            }
            if len(room["players"]) == 2 and room["phase"] == "waiting":
                room["phase"] = "rolling"
            payloads = self._payloads(room)
        await self._send_payloads(payloads)
        return True, ""

    async def leave(self, room_code, player_id, websocket):
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return
            player = room["players"].get(player_id)
            if player and player["socket"] is websocket:
                room["players"].pop(player_id, None)
                room["dice"].pop(player_id, None)
                room["rematch_ready"].discard(player_id)
            if not room["players"]:
                self.rooms.pop(room_code, None)
                return
            room.update(
                phase="waiting",
                turn_id=None,
                current_bid=None,
                outcome=None,
            )
            room["dice"] = {}
            payloads = self._payloads(room)
        await self._send_payloads(payloads)

    async def handle(self, room_code, player_id, message):
        error = None
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room or player_id not in room["players"]:
                return "房间已经失效"
            action = message.get("type")
            if action == "roll":
                error = self._roll(room, player_id, message.get("values"))
            elif action == "bid":
                error = self._bid(room, player_id, message)
            elif action == "challenge":
                error = self._challenge(room, player_id)
            elif action == "rematch":
                error = self._rematch(room, player_id)
            elif action == "ping":
                return None
            else:
                error = "不支持的游戏操作"
            payloads = self._payloads(room) if not error else []
        if not error:
            await self._send_payloads(payloads)
        return error

    @staticmethod
    def _roll(room, player_id, values):
        if room["phase"] != "rolling":
            return "现在不能摇骰子"
        if player_id in room["dice"]:
            return "你已经摇过了"
        if (
            not isinstance(values, list)
            or len(values) != DICE_PER_PLAYER
            or any(not isinstance(value, int) or value < 1 or value > 6 for value in values)
        ):
            return "骰子结果不正确"
        room["dice"][player_id] = values
        if len(room["dice"]) == len(room["players"]) == 2:
            room["phase"] = "bidding"
            player_ids = list(room["players"])
            room["turn_id"] = player_ids[room["round"] % len(player_ids)]
        return None

    @staticmethod
    def _bid(room, player_id, message):
        if room["phase"] != "bidding" or room["turn_id"] != player_id:
            return "还没轮到你叫骰"
        bid = {
            "quantity": int(message.get("quantity") or 0),
            "face": int(message.get("face") or 0),
            "bidder_id": player_id,
        }
        if bid["quantity"] > len(room["players"]) * DICE_PER_PLAYER:
            return "叫骰数量超过了桌面骰子总数"
        if not is_higher_bid(room["current_bid"], bid):
            return "新叫法必须高于当前叫法"
        room["current_bid"] = bid
        player_ids = list(room["players"])
        room["turn_id"] = player_ids[(player_ids.index(player_id) + 1) % len(player_ids)]
        return None

    @staticmethod
    def _challenge(room, player_id):
        if (
            room["phase"] != "bidding"
            or room["turn_id"] != player_id
            or not room["current_bid"]
        ):
            return "现在还不能开盅"
        bid = room["current_bid"]
        all_values = [value for values in room["dice"].values() for value in values]
        actual_count = sum(
            value == bid["face"] or (bid["face"] != 1 and value == 1)
            for value in all_values
        )
        bid_succeeded = actual_count >= bid["quantity"]
        winner_id = bid["bidder_id"] if bid_succeeded else player_id
        loser_id = player_id if bid_succeeded else bid["bidder_id"]
        room["outcome"] = {
            "actual_count": actual_count,
            "bid_succeeded": bid_succeeded,
            "winner_id": winner_id,
            "loser_id": loser_id,
        }
        room["phase"] = "finished"
        room["turn_id"] = None
        room["rematch_ready"] = set()
        return None

    @staticmethod
    def _rematch(room, player_id):
        if room["phase"] != "finished":
            return "本局还没有结束"
        room["rematch_ready"].add(player_id)
        if len(room["rematch_ready"]) == len(room["players"]) == 2:
            room["round"] += 1
            room["phase"] = "rolling"
            room["dice"] = {}
            room["turn_id"] = None
            room["current_bid"] = None
            room["outcome"] = None
            room["rematch_ready"] = set()
        return None

    @staticmethod
    def _payloads(room):
        public_players = [
            {
                "id": player["id"],
                "name": player["name"],
                "rolled": player["id"] in room["dice"],
                "rematch_ready": player["id"] in room["rematch_ready"],
            }
            for player in room["players"].values()
        ]
        payloads = []
        for player_id, player in room["players"].items():
            payload = {
                "type": "room_state",
                "room_code": room["room_code"],
                "phase": room["phase"],
                "players": public_players,
                "turn_id": room["turn_id"],
                "current_bid": room["current_bid"],
                "outcome": room["outcome"],
                "my_dice": room["dice"].get(player_id),
                "all_dice": room["dice"] if room["phase"] == "finished" else None,
            }
            payloads.append((player["socket"], payload))
        return payloads

    @staticmethod
    async def _send_payloads(payloads):
        for websocket, payload in payloads:
            try:
                await websocket.send_json(payload)
            except Exception:
                pass


order_event_hub = OrderEventHub()
dice_room_manager = DiceRoomManager()
