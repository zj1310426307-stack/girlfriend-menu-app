"""Freeze the public route/method surface during router modularization."""

from test_api import app


EXPECTED_HTTP_ROUTES = {
    tuple(line.split(" ", 1))
    for line in """
DELETE /api/couple/dates/{date_id}
DELETE /api/couple/memories/{memory_id}
DELETE /api/dishes/{dish_id}
DELETE /api/favorites/{dish_id}
GET /api/admin/dashboard
GET /api/admin/games/stats
GET /api/admin/orders
GET /api/bootstrap
GET /api/couple/dates
GET /api/couple/memories
GET /api/couple/profile
GET /api/couple/score
GET /api/couple/score/history
GET /api/couple/statistics
GET /api/couple/tasks/today
GET /api/dishes
GET /api/dishes/{dish_id}
GET /api/favorites
GET /api/games
GET /api/games/achievements
GET /api/games/active
GET /api/games/ai/players
GET /api/games/ai/summary
GET /api/games/chess/{game_id}/history
GET /api/games/chess/{room_code}/state
GET /api/games/flight/{room_code}/state
GET /api/games/memories/my
GET /api/games/ranking
GET /api/games/records/my
GET /api/games/records/{record_id}/replay
GET /api/games/rooms/{room_code}
GET /api/games/tasks/my
GET /api/games/{room_code}/state
GET /api/health
GET /api/images/{image_id}
GET /api/notifications
GET /api/notifications/unread-count
GET /api/orders
GET /api/orders/me
GET /api/orders/my/{legacy_customer_id}
GET /api/orders/{order_id}
GET /api/orders/{order_id}/review
GET /api/ready
GET /api/stats/dishes
GET /api/stats/favorite-ranking
GET /api/stats/recent
GET /api/stats/summary
GET /api/users/me
PATCH /api/notifications/{notification_id}/read
PATCH /api/orders/{order_id}/status
POST /api/admin/login
POST /api/admin/orders/{order_id}/rollback
POST /api/couple/dates
POST /api/couple/memories
POST /api/couple/score/add
POST /api/couple/tasks/{task_id}/complete
POST /api/customers/claim-legacy
POST /api/customers/recover
POST /api/customers/refresh
POST /api/customers/revoke
POST /api/customers/session
POST /api/customers/wechat-session
POST /api/dishes
POST /api/favorites/{dish_id}
POST /api/games/animal/create
POST /api/games/animal/join
POST /api/games/animal/move
POST /api/games/chess/create
POST /api/games/chess/join
POST /api/games/chess/move
POST /api/games/dice/rooms
POST /api/games/flight/action
POST /api/games/flight/create
POST /api/games/flight/join
POST /api/games/landlord/action
POST /api/games/landlord/create
POST /api/games/landlord/join
POST /api/games/reconnect
POST /api/games/reconnect/token
POST /api/games/rooms
POST /api/games/tasks/{task_id}/complete
POST /api/games/{game_type}/ai/move
POST /api/orders
POST /api/orders/repeat/{order_id}
POST /api/orders/{order_id}/repeat-preview
POST /api/orders/{order_id}/review
POST /api/upload/image
POST /api/users/presence
PUT /api/dishes/{dish_id}
PUT /api/users/me
""".strip().splitlines()
}

EXPECTED_WEBSOCKET_ROUTES = {
    "/ws/admin/orders",
    "/ws/game/{room_code}",
    "/ws/games/dice/{room_code}",
}


def test_http_route_method_contract_is_unchanged():
    """Freeze every current HTTP operation, including the additive V3 bootstrap."""
    actual_operations = [
        (method, route.path)
        for route in app.routes
        if route.path.startswith("/api")
        for method in sorted(getattr(route, "methods", set()) or set())
    ]
    assert set(actual_operations) == EXPECTED_HTTP_ROUTES
    assert len(actual_operations) == len(EXPECTED_HTTP_ROUTES)


def test_websocket_path_contract_is_unchanged():
    """Freeze all three deployed WebSocket paths without inspecting internals."""
    actual_paths = [route.path for route in app.routes if route.path.startswith("/ws")]
    assert set(actual_paths) == EXPECTED_WEBSOCKET_ROUTES
    assert len(actual_paths) == len(EXPECTED_WEBSOCKET_ROUTES)
