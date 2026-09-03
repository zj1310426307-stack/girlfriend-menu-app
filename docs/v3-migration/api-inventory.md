# LoveOS V3 API 基线清单

审计日期：2026-08-17
来源：运行中的 FastAPI 路由对象，而非文本猜测

## 数量口径

| 类型 | 数量 | 说明 |
| --- | ---: | --- |
| `/api/*` HTTP | 88 | V3 兼容门槛使用此口径 |
| WebSocket | 3 | 2 个游戏协议、1 个管理员通知协议 |
| 根业务路由 | 1 | `GET /` |
| FastAPI 内置文档路由 | 4 | `/docs`、`/redoc`、OpenAPI 等，不计业务 API |

因此应用业务 HTTP 路由共 89 个；历史 Precheck 的“HTTP = 88”是只统计 `/api` 路径，结论正确。

V3 当前增量：新增 `GET /api/bootstrap`，所以当前 `/api/*` HTTP 为 89，业务 HTTP 总数为 90；下方清单继续冻结 V2 的 89 个 method/path 组合，作为必须保留的兼容子集。

## 完整 HTTP 基线

```text
GET     /
GET     /api/admin/dashboard
GET     /api/admin/games/stats
POST    /api/admin/login
GET     /api/admin/orders
POST    /api/admin/orders/{order_id}/rollback
GET     /api/couple/dates
POST    /api/couple/dates
DELETE  /api/couple/dates/{date_id}
GET     /api/couple/memories
POST    /api/couple/memories
DELETE  /api/couple/memories/{memory_id}
GET     /api/couple/profile
GET     /api/couple/score
POST    /api/couple/score/add
GET     /api/couple/score/history
GET     /api/couple/statistics
GET     /api/couple/tasks/today
POST    /api/couple/tasks/{task_id}/complete
POST    /api/customers/claim-legacy
POST    /api/customers/recover
POST    /api/customers/refresh
POST    /api/customers/revoke
POST    /api/customers/session
GET     /api/dishes
POST    /api/dishes
DELETE  /api/dishes/{dish_id}
GET     /api/dishes/{dish_id}
PUT     /api/dishes/{dish_id}
GET     /api/favorites
DELETE  /api/favorites/{dish_id}
POST    /api/favorites/{dish_id}
GET     /api/games
GET     /api/games/achievements
GET     /api/games/active
GET     /api/games/ai/players
GET     /api/games/ai/summary
POST    /api/games/animal/create
POST    /api/games/animal/join
POST    /api/games/animal/move
POST    /api/games/chess/create
POST    /api/games/chess/join
POST    /api/games/chess/move
GET     /api/games/chess/{game_id}/history
GET     /api/games/chess/{room_code}/state
POST    /api/games/dice/rooms
POST    /api/games/flight/action
POST    /api/games/flight/create
POST    /api/games/flight/join
GET     /api/games/flight/{room_code}/state
POST    /api/games/landlord/action
POST    /api/games/landlord/create
POST    /api/games/landlord/join
GET     /api/games/memories/my
GET     /api/games/ranking
POST    /api/games/reconnect
POST    /api/games/reconnect/token
GET     /api/games/records/my
GET     /api/games/records/{record_id}/replay
POST    /api/games/rooms
GET     /api/games/rooms/{room_code}
GET     /api/games/tasks/my
POST    /api/games/tasks/{task_id}/complete
POST    /api/games/{game_type}/ai/move
GET     /api/games/{room_code}/state
GET     /api/health
GET     /api/images/{image_id}
GET     /api/notifications
GET     /api/notifications/unread-count
PATCH   /api/notifications/{notification_id}/read
GET     /api/orders
POST    /api/orders
GET     /api/orders/me
GET     /api/orders/my/{legacy_customer_id}
POST    /api/orders/repeat/{order_id}
GET     /api/orders/{order_id}
POST    /api/orders/{order_id}/repeat-preview
GET     /api/orders/{order_id}/review
POST    /api/orders/{order_id}/review
PATCH   /api/orders/{order_id}/status
GET     /api/ready
GET     /api/stats/dishes
GET     /api/stats/favorite-ranking
GET     /api/stats/recent
GET     /api/stats/summary
POST    /api/upload/image
GET     /api/users/me
PUT     /api/users/me
POST    /api/users/presence
```

## WebSocket 基线

```text
WS /ws/admin/orders
WS /ws/game/{room_code}
WS /ws/games/dice/{room_code}
```

## 兼容策略

- 上述 method + path 组合全部成为不可无意删除的快照。
- V3 新增接口不改变旧接口响应结构、认证头或状态码。
- 旧游戏专用路径继续作为 adapter；内部可以转发到插件注册表。
- WebSocket 消息类型、首帧状态、版本号、重连行为由现有协议测试保护。
- `/api/bootstrap` 作为新增接口，不替代 `/api/dishes`、排行榜或积分接口。
- OpenAPI 3.1 规范由 FastAPI 应用直接导出；以后生成客户端也以该规范为唯一来源。

## 已有契约证据

- `backend/tests/test_router_contract.py`
- `backend/tests/test_websocket_protocol_contract.py`
- `backend/tests/test_websocket_first_state.py`
- `backend/tests/test_realtime_facade_contract.py`
- `miniprogram/scripts/customer-session-contract-test.cjs`
- `miniprogram/scripts/game-socket-test.cjs`

V3 将补充全量路由快照测试，避免只覆盖几个代表性路径。
