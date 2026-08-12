# Phase 2B CRUD Map

Baseline: `backend/crud.py` at commit `5fe1cf8` (37 functions).

Action meanings:

- `MOVE`: move SQL access to Repository and orchestration to Service during Phase 2B.
- `WRAP`: keep a compatibility facade while callers migrate.
- `KEEP`: retain in `crud.py` because the responsibility is intentionally outside the current move.
- `DEFER`: game/realtime persistence reserved for Phase 2C.

| Function | Domain | Called By | DB Tables | Mutates | Phase 2B Action |
|---|---|---|---|---|---|
| `touch_game_room` | GAME_ROOM | game services/core | `game_rooms` | object only | DEFER |
| `list_games` | GAME_STATE | games router | `games` | no | DEFER |
| `get_game` | GAME_STATE | `create_game_room` | `games` | no | DEFER |
| `create_game_room` | GAME_ROOM | games router/services/core | `games`, `game_rooms` | yes | DEFER |
| `get_game_room` | GAME_ROOM | games/WS/services/core | `game_rooms` | no | DEFER |
| `update_game_room_status` | GAME_ROOM | WebSocket | `game_rooms` | yes | DEFER |
| `list_game_players` | GAME_PLAYER | games/WS | `game_rooms`, `game_players` | no | DEFER |
| `join_game_room` | GAME_PLAYER | games/WS/services/core | `game_rooms`, `game_players`, `notifications` | yes | DEFER |
| `issue_room_session_token` | GAME_PLAYER | WebSocket | `game_players`, `game_rooms` | yes | DEFER |
| `mark_game_player_disconnected` | GAME_PLAYER | WebSocket | `game_players`, `game_rooms` | yes | DEFER |
| `expire_stale_game_rooms` | GAME_ROOM | maintenance loop | `game_rooms`, `game_players`, `game_reconnect_tokens` | yes | DEFER |
| `_game_record_query` | GAME_RECORD | record helpers | `game_records`, `game_rooms`, `game_players` | no | DEFER |
| `finish_game_room` | GAME_RECORD | game/WS services | `game_rooms`, `game_records`, `game_players` | yes | DEFER |
| `list_game_records` | GAME_RECORD | games router/tests | `game_records`, `game_rooms`, `game_players` | no | DEFER |
| `game_stats` | STATS | admin router/tests | game, score, task and achievement tables | no | DEFER |
| `list_dishes` | DISH | dishes router | `dishes` | no | MOVE |
| `get_dish` | DISH | dishes/favorite/order helpers | `dishes` | no | MOVE |
| `create_dish` | DISH | dishes router | `dishes` | yes | MOVE |
| `update_dish` | DISH | dishes router | `dishes` | yes | MOVE |
| `delete_dish` | DISH | dishes router | `dishes` | yes (soft delete) | MOVE |
| `list_favorite_dishes` | FAVORITE | dishes router | `favorite_dishes`, `dishes` | no | MOVE |
| `add_favorite_dish` | FAVORITE | dishes router | `favorite_dishes`, `dishes` | yes | MOVE |
| `remove_favorite_dish` | FAVORITE | dishes router | `favorite_dishes` | yes | MOVE |
| `create_order` | ORDER | orders router | `orders`, `order_items`, `dishes`, `love_scores` | yes | MOVE |
| `repeat_order_draft` | ORDER | orders router | `orders`, `order_items`, `dishes` | no | MOVE |
| `list_orders` | ORDER | orders router | `orders` | no | MOVE |
| `list_admin_orders` | ADMIN_ORDER_QUERY | orders router | `orders`, `order_items` | no | MOVE |
| `list_customer_orders` | ORDER | orders router | `orders` | no | MOVE |
| `get_order` | ORDER | orders/review helpers | `orders` | no | MOVE |
| `update_order_status` | ORDER | orders router | `orders`, `order_status_events`, score/task tables | yes | MOVE |
| `rollback_order_status` | ORDER | orders router | `orders`, `order_status_events` | yes | MOVE |
| `get_review` | REVIEW | orders router | `orders`, `reviews` | no | MOVE |
| `create_review` | REVIEW | orders router | `orders`, `reviews`, score/task tables | yes | MOVE |
| `get_stats_summary` | STATS | admin router | `orders` | no | MOVE |
| `get_dish_stats` | STATS | admin router | `orders`, `order_items` | no | MOVE |
| `get_recent_orders` | STATS | admin router | `orders` | no | MOVE |
| `get_favorite_ranking` | STATS | dishes router | dishes, orders, items, reviews, favorites | no | KEEP |

## First-round totals

- Total functions: 37
- MOVE: 21
- KEEP: 1
- DEFER: 15
- WRAP: 0 in the baseline map; compatibility wrappers are introduced as moved
  functions leave their original implementations.

This first execution round implements only the five Dish functions and three
Favorite functions. Review, Order and non-game Stats remain untouched until the
next explicit instruction.
