"""Small process-local event hubs unrelated to game rule state."""

import asyncio

from fastapi import WebSocket


class OrderEventHub:
    """Broadcast order changes to authenticated administrator sockets."""

    def __init__(self):
        self.connections: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def add(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.connections.add(websocket)

    async def remove(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.connections.discard(websocket)

    async def broadcast(self, event_type: str, order_id: int) -> None:
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


order_event_hub = OrderEventHub()


__all__ = ["OrderEventHub", "order_event_hub"]
