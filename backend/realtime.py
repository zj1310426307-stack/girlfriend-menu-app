import asyncio
from copy import deepcopy
import secrets
import time
from collections import OrderedDict

from fastapi import WebSocket

from ai.gomoku_ai import GomokuAI
from gomoku import GomokuError, GomokuGame
from core.game_state_store import game_state_store
from dice_rules import is_higher_bid, resolve_challenge


ROOM_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
DICE_PER_PLAYER = 5
GOMOKU_REWARDS = (
    "赢家决定今晚加一道菜",
    "输家负责洗碗一次",
    "互相说一句今天最喜欢对方的地方",
    "赢家可以指定下一次约会的小任务",
)
GOMOKU_AI_ID = "ai_gomoku"


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
    """Process-local WebSocket transport for database-leased real-time rooms.

    PostgreSQL owns room metadata and recoverable snapshots. A database lease
    ensures only one process mutates a room while socket objects stay local.
    """

    def __init__(self):
        self.rooms = {}
        self.lock = asyncio.Lock()
        self._pending_snapshots: dict[str, dict] = {}
        self._persistence_tasks: dict[str, asyncio.Task] = {}

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
            "action_history": [],
            "state_version": 1,
            "last_activity_at": time.time(),
            "mode": "couple",
            "difficulty": "rule",
        }
        if game_type == "gomoku":
            room["gomoku"] = GomokuGame()
        return room

    async def ensure_room(self, room_code, game_type, max_players):
        normalized = str(room_code).strip().upper()
        existed = await self.has_room(normalized)
        result = await self.create_room(normalized, game_type, max_players)
        if not existed:
            # PostgreSQL is the durable source. Run its lookup off the event
            # loop so one cold room cannot freeze unrelated live sockets.
            snapshot = await asyncio.to_thread(game_state_store.get, normalized)
            if snapshot and snapshot.get("game_type") == game_type:
                async with self.lock:
                    self._restore_snapshot(self.rooms[normalized], snapshot)
        return result

    @staticmethod
    def _snapshot(room):
        """Create a Redis-safe room snapshot without socket objects."""
        players = [
            {
                "id": item["id"],
                "name": item.get("name", "玩家"),
                "protocol": item.get("protocol", "v2"),
                "seat": item.get("seat"),
                "color": item.get("color"),
            }
            for item in room["players"].values()
        ]
        started_at = room.get("started_at")
        elapsed_seconds = (
            max(0.0, time.monotonic() - float(started_at))
            if started_at is not None
            else None
        )
        return {
            "version": 2,
            "room_code": room["room_code"],
            "game_type": room["game_type"],
            "max_players": room["max_players"],
            "players": players,
            "scores": dict(room["scores"]),
            "dice": dict(room["dice"]),
            "phase": room["phase"],
            "turn_id": room["turn_id"],
            "current_bid": room["current_bid"],
            "outcome": room["outcome"],
            "rematch_ready": list(room["rematch_ready"]),
            "round": room["round"],
            "elapsed_seconds": elapsed_seconds,
            "completed_event": deepcopy(room.get("completed_event")),
            "action_history": list(room.get("action_history") or []),
            "state_version": int(room.get("state_version") or 1),
            "last_activity_at": room.get("last_activity_at") or time.time(),
            "mode": room.get("mode", "couple"),
            "difficulty": room.get("difficulty", "rule"),
            "engine": room["gomoku"].serialize() if room["game_type"] == "gomoku" else None,
        }

    @classmethod
    def _cache_room(cls, room):
        game_state_store.set(room["room_code"], cls._snapshot(room), ttl_seconds=900)

    async def _persist_snapshot(self, room_code: str, snapshot: dict) -> None:
        """Coalesce rapid actions while preserving an awaited durable boundary."""
        task = self._queue_snapshot(room_code, snapshot)
        await asyncio.shield(task)

    def _queue_snapshot(self, room_code: str, snapshot: dict) -> asyncio.Task:
        """Schedule a write-behind snapshot and return the room's drain task."""
        self._pending_snapshots[room_code] = snapshot
        task = self._persistence_tasks.get(room_code)
        if task is None or task.done():
            task = asyncio.create_task(self._drain_snapshots(room_code))
            self._persistence_tasks[room_code] = task
        return task

    async def flush_persistence(self, room_code: str) -> None:
        """Wait until every snapshot queued for one room is durably mirrored."""
        while True:
            task = self._persistence_tasks.get(room_code)
            if task is None:
                return
            await asyncio.shield(task)
            if room_code not in self._pending_snapshots:
                return

    async def _drain_snapshots(self, room_code: str) -> None:
        """Write the newest queued snapshot until no newer room state remains."""
        try:
            while True:
                snapshot = self._pending_snapshots.pop(room_code, None)
                if snapshot is None:
                    return
                await asyncio.to_thread(
                    game_state_store.set,
                    room_code,
                    snapshot,
                    900,
                )
        finally:
            self._persistence_tasks.pop(room_code, None)
            if room_code in self._pending_snapshots:
                self._queue_snapshot(room_code, self._pending_snapshots[room_code])

    @staticmethod
    def _restore_snapshot(room, snapshot):
        """Restore JSON-only state; sockets always reconnect separately."""
        room["scores"] = dict(snapshot.get("scores") or {})
        room["dice"] = dict(snapshot.get("dice") or {})
        room["phase"] = snapshot.get("phase") or "waiting"
        room["turn_id"] = snapshot.get("turn_id")
        room["current_bid"] = snapshot.get("current_bid")
        room["outcome"] = snapshot.get("outcome")
        room["rematch_ready"] = set(snapshot.get("rematch_ready") or [])
        room["round"] = int(snapshot.get("round") or 0)
        elapsed_seconds = snapshot.get("elapsed_seconds")
        room["started_at"] = (
            time.monotonic() - max(0.0, float(elapsed_seconds))
            if elapsed_seconds is not None
            else None
        )
        room["completed_event"] = deepcopy(snapshot.get("completed_event"))
        room["action_history"] = list(snapshot.get("action_history") or [])
        room["state_version"] = int(snapshot.get("state_version") or 1)
        room["last_activity_at"] = float(snapshot.get("last_activity_at") or time.time())
        room["mode"] = snapshot.get("mode") or "couple"
        room["difficulty"] = snapshot.get("difficulty") or "rule"
        for raw in snapshot.get("players") or []:
            room["players"][raw["id"]] = {
                **raw,
                "socket": None,
                "connected": False,
            }
        if room["game_type"] == "gomoku" and snapshot.get("engine"):
            raw = snapshot["engine"]
            engine = GomokuGame()
            for player in raw.get("players") or []:
                engine.add_player(player["id"])
            engine.board = [list(row) for row in raw.get("board") or engine.board]
            engine.phase = raw.get("phase", engine.phase)
            engine.turn_id = raw.get("turn_id")
            engine.winner_id = raw.get("winner_id")
            engine.last_move = raw.get("last_move")
            engine.move_count = int(raw.get("move_count") or 0)
            engine.move_history = list(raw.get("move_history") or [])
            engine.round = int(raw.get("round") or 1)
            engine.is_draw = bool(raw.get("is_draw"))
            room["gomoku"] = engine

    async def has_room(self, room_code):
        async with self.lock:
            return room_code in self.rooms

    async def active_room_codes(self) -> list[str]:
        """Return rooms with at least one live human socket for lease heartbeat."""
        async with self.lock:
            return [
                code
                for code, room in self.rooms.items()
                if any(
                    player.get("connected")
                    for player in room["players"].values()
                    if not str(player.get("id", "")).startswith("ai_")
                )
            ]

    async def has_live_connections(self, room_code: str) -> bool:
        """Tell the gateway whether it is safe to release one room lease."""
        normalized = room_code.strip().upper()
        async with self.lock:
            room = self.rooms.get(normalized)
            return bool(
                room
                and any(
                    player.get("connected")
                    for player in room["players"].values()
                    if not str(player.get("id", "")).startswith("ai_")
                )
            )

    async def cleanup_expired(self, room_codes=None, ttl_seconds=900):
        """Drop only inactive socket state; durable records remain in the database."""
        now = time.time()
        requested = {str(code).upper() for code in (room_codes or [])}
        async with self.lock:
            expired = []
            for code, room in list(self.rooms.items()):
                no_live_socket = not any(
                    player.get("connected")
                    for player in room["players"].values()
                    if not str(player.get("id", "")).startswith("ai_")
                )
                idle = now - float(room.get("last_activity_at") or now) >= ttl_seconds
                if no_live_socket and (code in requested or idle):
                    self.rooms.pop(code, None)
                    expired.append(code)
            return expired

    async def restore_players(self, room_code, stored_players):
        """Restore persistent seats before sockets reconnect after a warm restart."""
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return
            for stored in sorted(stored_players, key=lambda item: item.seat):
                player_id = stored.player_id
                color = None
                if room["game_type"] == "gomoku":
                    engine = room["gomoku"]
                    if player_id not in engine.players:
                        color = engine.add_player(player_id)
                    else:
                        color = "black" if engine.players[player_id] == 1 else "white"
                room["players"].setdefault(
                    player_id,
                    {
                        "id": player_id,
                        "name": "五子棋 AI" if player_id.startswith("ai_") else f"玩家{stored.seat}",
                        "socket": None,
                        "protocol": "v2",
                        "connected": player_id.startswith("ai_"),
                        "seat": stored.seat,
                        "color": color,
                    },
                )
                room["scores"][player_id] = stored.score
                if room["game_type"] == "gomoku" and player_id == GOMOKU_AI_ID:
                    # The synthetic seat is durable even without Redis, so a
                    # cold restart can still resume the room in AI mode. The
                    # selected difficulty falls back to the safe rule level.
                    room["mode"] = "ai"
                    room["difficulty"] = room.get("difficulty") or "rule"
            if room["game_type"] == "gomoku":
                engine = room["gomoku"]
                room["phase"] = engine.phase
                room["turn_id"] = engine.turn_id
                if engine.phase == "playing" and room["started_at"] is None:
                    room["started_at"] = time.monotonic()
            # The seats already come from PostgreSQL. Persisting the identical
            # snapshot here adds a full write before the first WebSocket state
            # without improving recovery guarantees.

    async def configure_gomoku_ai(self, room_code: str, difficulty: str = "rule") -> None:
        """Mark a Gomoku room as solo mode and restore its synthetic opponent."""
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room or room["game_type"] != "gomoku":
                return
            room["mode"] = "ai"
            room["difficulty"] = difficulty
            engine = room["gomoku"]
            if GOMOKU_AI_ID not in engine.players:
                engine.add_player(GOMOKU_AI_ID)
            room["players"][GOMOKU_AI_ID] = {
                **room["players"].get(GOMOKU_AI_ID, {}),
                "id": GOMOKU_AI_ID,
                "name": "五子棋 AI",
                "socket": None,
                "protocol": "v2",
                "connected": True,
                "seat": 2,
                "color": "white",
            }
            room["scores"].setdefault(GOMOKU_AI_ID, 0)
            room["phase"] = engine.phase
            room["turn_id"] = engine.turn_id
            room["started_at"] = room["started_at"] or time.monotonic()
            snapshot = self._snapshot(room)
        await self._persist_snapshot(room_code, snapshot)

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
            room["last_activity_at"] = time.time()
            room["scores"].setdefault(player_id, 0)
            if room["game_type"] == "gomoku":
                room["phase"] = room["gomoku"].phase
                room["turn_id"] = room["gomoku"].turn_id
                if room["phase"] == "playing" and room["started_at"] is None:
                    room["started_at"] = time.monotonic()
            elif len(room["players"]) == room["max_players"] and room["phase"] == "waiting":
                room["phase"] = "rolling"
                room["started_at"] = time.monotonic()
            payloads = self._payloads(room)
            snapshot = self._snapshot(room)
        await self._send_payloads(payloads)
        # Joining is already durable in ``game_players``. Send the first
        # viewer-filtered state immediately, then mirror the recoverable engine
        # snapshot off the event loop. No game action can be lost here.
        self._queue_snapshot(room_code, snapshot)
        return True, ""

    async def leave(self, room_code, player_id, websocket):
        snapshot = None
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return
            player = room["players"].get(player_id)
            if player and player["socket"] is websocket:
                player["socket"] = None
                player["connected"] = False
                room["last_activity_at"] = time.time()
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
                payloads = self._payloads(room)
            snapshot = self._snapshot(room)
        await self._send_payloads(payloads)
        if snapshot:
            await self._persist_snapshot(room_code, snapshot)

    async def handle(self, room_code, player_id, message):
        error = None
        should_run_gomoku_ai = False
        snapshot = None
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
                room["state_version"] = int(room.get("state_version") or 0) + 1
                room["last_activity_at"] = time.time()
                should_run_gomoku_ai = (
                    room["game_type"] == "gomoku"
                    and room.get("mode") == "ai"
                    and room["phase"] == "playing"
                    and room["turn_id"] == GOMOKU_AI_ID
                )
                snapshot = self._snapshot(room)
        if not error:
            await self._send_payloads(payloads)
            self._queue_snapshot(room_code, snapshot)
            if snapshot.get("phase") == "finished":
                await self.flush_persistence(room_code)
        if should_run_gomoku_ai:
            # Let the human stone settle visually before broadcasting the AI
            # response. State is rechecked after the delay to remain safe.
            await asyncio.sleep(0.28)
            async with self.lock:
                room = self.rooms.get(room_code)
                if (
                    room
                    and room.get("mode") == "ai"
                    and room.get("phase") == "playing"
                    and room.get("turn_id") == GOMOKU_AI_ID
                ):
                    decision = GomokuAI(room.get("difficulty", "rule")).choose_action(
                        room["gomoku"].serialize(), GOMOKU_AI_ID
                    )
                    if decision.get("action") == "MOVE":
                        error = self._gomoku_move(room, GOMOKU_AI_ID, decision)
                    if not error:
                        room["state_version"] = int(room.get("state_version") or 0) + 1
                        room["last_activity_at"] = time.time()
                        payloads = self._payloads(room)
                        snapshot = self._snapshot(room)
                    else:
                        payloads = []
            if not error:
                await self._send_payloads(payloads)
                self._queue_snapshot(room_code, snapshot)
                if snapshot.get("phase") == "finished":
                    await self.flush_persistence(room_code)
        return error

    async def consume_completed_event(self, room_code):
        async with self.lock:
            room = self.rooms.get(room_code)
            if not room:
                return None
            event = room.get("completed_event")
            room["completed_event"] = None
            return event

    async def acknowledge_completed_event(self, room_code):
        """Persist that a consumed completion event finished settlement.

        Until this acknowledgement, PostgreSQL intentionally retains the
        pending event so a process crash can replay the idempotent settlement.
        """
        async with self.lock:
            room = self.rooms.get(room_code)
            snapshot = self._snapshot(room) if room else None
        if snapshot:
            await self._persist_snapshot(room_code, snapshot)

    async def restore_completed_event(self, room_code, event):
        """Put a failed settlement back so the next room action can retry it."""
        async with self.lock:
            room = self.rooms.get(room_code)
            if room and room.get("completed_event") is None:
                room["completed_event"] = event
                snapshot = self._snapshot(room)
            else:
                snapshot = None
        if snapshot:
            await self._persist_snapshot(room_code, snapshot)

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
    def _state_for_player(room, player_id):
        """Build the same viewer-filtered state used by live broadcasts."""
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
            return {
                **engine_state,
                "players": public_players,
                "outcome": room["outcome"],
                "round_id": f"{room['room_code']}:{engine_state.get('round', 1)}",
                "server_timestamp": int(time.time() * 1000),
                "state_version": int(room.get("state_version") or 1),
                "mode": room.get("mode", "couple"),
                "difficulty": room.get("difficulty", "rule"),
            }
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
        return {
            "phase": room["phase"],
            "players": public_players,
            "turn_id": room["turn_id"],
            "current_bid": room["current_bid"],
            "outcome": room["outcome"],
            "round": room["round"] + 1,
            "round_id": f"{room['room_code']}:{room['round'] + 1}",
            "server_timestamp": int(time.time() * 1000),
            "state_version": int(room.get("state_version") or 1),
            "my_dice": deepcopy(room["dice"].get(player_id)),
            "all_dice": deepcopy(room["dice"]) if room["phase"] == "finished" else None,
        }

    async def recovery_state(self, room_code, player_id):
        """Return a reconnect snapshot without exposing private opponent data."""
        normalized = str(room_code).strip().upper()
        async with self.lock:
            room = self.rooms.get(normalized)
            if not room or player_id not in room["players"]:
                return None
            return deepcopy(self._state_for_player(room, player_id))

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
                    "move_history": list(engine.move_history),
                    "final_state": engine.serialize(),
                    "mode": room.get("mode", "couple"),
                    "difficulty": room.get("difficulty", "rule"),
                },
            }
        return None

    @staticmethod
    def _gomoku_rematch(room, player_id):
        if room["phase"] != "finished":
            return "本局还没有结束"
        room["rematch_ready"].add(player_id)
        if room.get("mode") == "ai":
            room["rematch_ready"].add(GOMOKU_AI_ID)
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
    def _roll(room, player_id, values=None):
        if room["phase"] != "rolling":
            return "现在不能摇骰子"
        if player_id in room["dice"]:
            return "你已经摇过了"
        # The client only requests a roll. Winning randomness is generated here.
        values = [secrets.randbelow(6) + 1 for _ in range(DICE_PER_PLAYER)]
        room["dice"][player_id] = values
        room["action_history"].append({
            "number": len(room["action_history"]) + 1,
            "type": "ROLL",
            "player_id": player_id,
            "values": list(values),
        })
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
        room["action_history"].append({
            "number": len(room["action_history"]) + 1,
            "type": "BID",
            **bid,
        })
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
        room["outcome"] = resolve_challenge(all_values, bid, player_id)
        actual_count = room["outcome"]["actual_count"]
        winner_id = room["outcome"]["winner_id"]
        loser_id = room["outcome"]["loser_id"]
        room["scores"][winner_id] = room["scores"].get(winner_id, 0) + 1
        room["phase"] = "finished"
        room["turn_id"] = None
        room["rematch_ready"] = set()
        room["action_history"].append({
            "number": len(room["action_history"]) + 1,
            "type": "CHALLENGE",
            "player_id": player_id,
            "actual_count": actual_count,
            "winner_id": winner_id,
        })
        duration = max(0, round(time.monotonic() - (room["started_at"] or time.monotonic())))
        room["completed_event"] = {
            "room_code": room["room_code"],
            "game_type": "dice",
            "round_number": room["round"] + 1,
            "players": list(room["players"]),
            "winner_id": winner_id,
            "duration": duration,
            "result": {
                **room["outcome"],
                "scores": dict(room["scores"]),
                "move_history": list(room["action_history"]),
                "all_dice": dict(room["dice"]),
            },
        }
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
            room["action_history"] = []
            room["started_at"] = time.monotonic()
        return None

    @staticmethod
    def _payloads(room):
        if room["game_type"] == "gomoku":
            state = GameRoomManager._state_for_player(room, next(iter(room["players"]), ""))
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
        payloads = []
        for player_id, player in room["players"].items():
            state = GameRoomManager._state_for_player(room, player_id)
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
