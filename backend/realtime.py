import asyncio
import secrets
import time
from collections import OrderedDict

from fastapi import WebSocket

from gomoku import GomokuError, GomokuGame


ROOM_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
DICE_PER_PLAYER = 5
GOMOKU_REWARDS = (
    "赢家决定今晚加一道菜",
    "输家负责洗碗一次",
    "互相说一句今天最喜欢对方的地方",
    "赢家可以指定下一次约会的小任务",
)


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


class GameRoomManager:
    """Shared in-memory transport for real-time games.

    Room metadata is persisted in ``game_rooms``; fast-changing board state and
    socket objects remain in memory. Dice and the server-authoritative Gomoku
    engine share the V2 protocol envelope and room lifecycle.
    """

    def __init__(self):
        self.rooms = {}
        self.lock = asyncio.Lock()

    async def create_room(self, room_code=None, game_type="dice", max_players=2):
        async with self.lock:
            if room_code:
                normalized = str(room_code).strip().upper()
                self.rooms.setdefault(
                    normalized,
                    self._new_room(normalized, game_type, max_players),
                )
                return normalized
            while True:
                room_code = "".join(secrets.choice(ROOM_ALPHABET) for _ in range(6))
                if room_code not in self.rooms:
                    self.rooms[room_code] = self._new_room(room_code, game_type, max_players)
                    return room_code

    @staticmethod
    def _new_room(room_code, game_type="dice", max_players=2):
        room = {
            "room_code": room_code,
            "game_type": game_type,
            "max_players": max_players,
            "players": OrderedDict(),
            "scores": {},
            "dice": {},
            "phase": "waiting",
            "turn_id": None,
            "current_bid": None,
            "outcome": None,
            "rematch_ready": set(),
            "round": 0,
            "started_at": None,
            "completed_event": None,
        }
        if game_type == "gomoku":
            room["gomoku"] = GomokuGame()
        return room

    async def ensure_room(self, room_code, game_type, max_players):
        return await self.create_room(room_code, game_type, max_players)

    async def has_room(self, room_code):
        async with self.lock:
            return room_code in self.rooms

    async def restore_players(self, room_code, stored_players):
        """Restore persistent seats before sockets reconnect after a warm restart."""
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room or room["game_type"] != "gomoku":
                return
            engine = room["gomoku"]
            for stored in sorted(stored_players, key=lambda item: item.seat):
                player_id = stored.player_id
                if player_id not in engine.players:
                    color = engine.add_player(player_id)
                else:
                    color = "black" if engine.players[player_id] == 1 else "white"
                room["players"].setdefault(
                    player_id,
                    {
                        "id": player_id,
                        "name": f"玩家{stored.seat}",
                        "socket": None,
                        "protocol": "v2",
                        "connected": False,
                        "seat": stored.seat,
                        "color": color,
                    },
                )
                room["scores"][player_id] = stored.score
            room["phase"] = engine.phase
            room["turn_id"] = engine.turn_id
            if engine.phase == "playing" and room["started_at"] is None:
                room["started_at"] = time.monotonic()

    async def join(
        self,
        room_code,
        player_id,
        player_name,
        websocket,
        protocol="v2",
        game_type=None,
    ):
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return False, "房间不存在或已经失效"
            if game_type and game_type != room["game_type"]:
                return False, "游戏类型与房间不匹配"
            if player_id not in room["players"] and len(room["players"]) >= room["max_players"]:
                return False, "房间已经满了"
            existing = room["players"].get(player_id, {})
            player = {
                **existing,
                "id": player_id,
                "name": player_name[:20] or existing.get("name") or "玩家",
                "socket": websocket,
                "protocol": protocol,
                "connected": True,
            }
            if room["game_type"] == "gomoku":
                engine = room["gomoku"]
                if player_id not in engine.players:
                    try:
                        player["color"] = engine.add_player(player_id)
                    except GomokuError as error:
                        return False, error.message
                else:
                    player["color"] = "black" if engine.players[player_id] == 1 else "white"
                player["seat"] = list(engine.players).index(player_id) + 1
            elif room["game_type"] != "dice":
                return False, "这个游戏协议还没有开放"
            room["players"][player_id] = player
            room["scores"].setdefault(player_id, 0)
            if room["game_type"] == "gomoku":
                room["phase"] = room["gomoku"].phase
                room["turn_id"] = room["gomoku"].turn_id
                if room["phase"] == "playing" and room["started_at"] is None:
                    room["started_at"] = time.monotonic()
            elif len(room["players"]) == room["max_players"] and room["phase"] == "waiting":
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
                if room["game_type"] == "gomoku":
                    player["socket"] = None
                    player["connected"] = False
                else:
                    room["players"].pop(player_id, None)
                    room["dice"].pop(player_id, None)
                    room["rematch_ready"].discard(player_id)
            if not room["players"]:
                self.rooms.pop(room_code, None)
                return
            if room["game_type"] == "gomoku":
                payloads = self._payloads(room)
                should_remove = not any(
                    item.get("connected") for item in room["players"].values()
                ) and room["phase"] == "waiting"
                if should_remove:
                    self.rooms.pop(room_code, None)
                    return
            else:
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
            requested_game = str(message.get("game") or "").lower()
            if requested_game and requested_game != room["game_type"]:
                return "游戏类型与房间不匹配"
            action = str(message.get("type") or "").lower()
            data = message.get("data") if isinstance(message.get("data"), dict) else message
            if room["game_type"] == "gomoku" and action == "move":
                error = self._gomoku_move(room, player_id, data)
            elif room["game_type"] == "gomoku" and action == "rematch":
                error = self._gomoku_rematch(room, player_id)
            elif action == "roll":
                error = self._roll(room, player_id, data.get("values"))
            elif action == "bid":
                error = self._bid(room, player_id, data)
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

    async def consume_completed_event(self, room_code):
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return None
            event = room.get("completed_event")
            room["completed_event"] = None
            return event

    async def restore_completed_event(self, room_code, event):
        """Put a failed settlement back so the next room action can retry it."""
        async with self.lock:
            room = self.rooms.get(room_code)
            if room and room.get("completed_event") is None:
                room["completed_event"] = event

    async def room_status(self, room_code):
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return "waiting"
            if room["phase"] == "finished":
                return "finished"
            if len(room["players"]) >= room["max_players"]:
                return "playing"
            return "waiting"

    @staticmethod
    def _gomoku_move(room, player_id, data):
        engine = room["gomoku"]
        try:
            engine.move(player_id, data.get("x"), data.get("y"))
        except GomokuError as error:
            return error.message
        room["phase"] = engine.phase
        room["turn_id"] = engine.turn_id
        if engine.phase == "finished":
            players = list(engine.players)
            winner_id = engine.winner_id
            loser_id = next((item for item in players if item != winner_id), None) if winner_id else None
            reward = secrets.choice(GOMOKU_REWARDS)
            room["outcome"] = {
                "winner_id": winner_id,
                "loser_id": loser_id,
                "is_draw": engine.is_draw,
                "reward": reward,
            }
            if winner_id:
                room["scores"][winner_id] = room["scores"].get(winner_id, 0) + 1
            room["rematch_ready"] = set()
            duration = max(0, round(time.monotonic() - (room["started_at"] or time.monotonic())))
            room["completed_event"] = {
                "room_code": room["room_code"],
                "game_type": "gomoku",
                "round_number": engine.round,
                "players": players,
                "winner_id": winner_id,
                "duration": duration,
                "result": {
                    "winner_id": winner_id,
                    "is_draw": engine.is_draw,
                    "move_count": engine.move_count,
                    "last_move": engine.last_move,
                    "reward": reward,
                    "scores": dict(room["scores"]),
                },
            }
        return None

    @staticmethod
    def _gomoku_rematch(room, player_id):
        if room["phase"] != "finished":
            return "本局还没有结束"
        room["rematch_ready"].add(player_id)
        if len(room["rematch_ready"]) == len(room["players"]) == room["max_players"]:
            engine = room["gomoku"]
            engine.reset()
            room["phase"] = engine.phase
            room["turn_id"] = engine.turn_id
            room["outcome"] = None
            room["rematch_ready"] = set()
            room["started_at"] = time.monotonic()
        return None

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
        if len(room["dice"]) == len(room["players"]) == room["max_players"]:
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
        room["scores"][winner_id] = room["scores"].get(winner_id, 0) + 1
        room["phase"] = "finished"
        room["turn_id"] = None
        room["rematch_ready"] = set()
        return None

    @staticmethod
    def _rematch(room, player_id):
        if room["phase"] != "finished":
            return "本局还没有结束"
        room["rematch_ready"].add(player_id)
        if len(room["rematch_ready"]) == len(room["players"]) == room["max_players"]:
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
        if room["game_type"] == "gomoku":
            engine_state = room["gomoku"].serialize()
            public_players = [
                {
                    "id": player["id"],
                    "name": player["name"],
                    "seat": player.get("seat"),
                    "color": player.get("color"),
                    "connected": bool(player.get("connected")),
                    "rematch_ready": player["id"] in room["rematch_ready"],
                    "score": room["scores"].get(player["id"], 0),
                }
                for player in room["players"].values()
            ]
            state = {
                **engine_state,
                "players": public_players,
                "outcome": room["outcome"],
            }
            return [
                (
                    player["socket"],
                    {
                        "type": "state",
                        "game": "gomoku",
                        "room_code": room["room_code"],
                        "data": state,
                    },
                )
                for player in room["players"].values()
                if player.get("socket") is not None
            ]
        public_players = [
            {
                "id": player["id"],
                "name": player["name"],
                "rolled": player["id"] in room["dice"],
                "rematch_ready": player["id"] in room["rematch_ready"],
                "score": room["scores"].get(player["id"], 0),
            }
            for player in room["players"].values()
        ]
        payloads = []
        for player_id, player in room["players"].items():
            state = {
                "phase": room["phase"],
                "players": public_players,
                "turn_id": room["turn_id"],
                "current_bid": room["current_bid"],
                "outcome": room["outcome"],
                "round": room["round"] + 1,
                "my_dice": room["dice"].get(player_id),
                "all_dice": room["dice"] if room["phase"] == "finished" else None,
            }
            if player.get("protocol") == "legacy":
                payload = {
                    "type": "room_state",
                    "room_code": room["room_code"],
                    **state,
                }
            else:
                payload = {
                    "type": "state",
                    "game": room["game_type"],
                    "room_code": room["room_code"],
                    "data": state,
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
game_room_manager = GameRoomManager()
# Compatibility alias for code imported before the unified V2.1 protocol.
dice_room_manager = game_room_manager
