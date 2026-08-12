# Phase 0 工程基线

> 采集时间：2026-08-11（Asia/Shanghai）
>
> 采集范围：本地 `main` 工作区，尚未实施 Phase 1 业务改动
> 目的：为后续安全收敛建立可复核、可回滚的事实基线

## 1. 版本与工作区

- Git commit：`f0e44c0ebff0caa952a0a681185acd5d281f151d`
- Commit subject：`stabilize games for 2.11.0`
- 源码版本：`2.11.0`
- Python：`3.12.13`
- Alembic head：`20260811_10`
- 工作区并非 clean：包含已完成但尚未提交的旧网页端/缓存清理、说明文档更新和上传测试隔离改动；Phase 1 必须保留这些改动。

## 2. 当前验证结果

- 后端：`70 passed`
- 小程序：`npm run build:weapp` 通过，Taro `4.2.0`
- 游戏契约：`npm run test:games` 通过
- 斗地主横屏契约：`npm run test:landlord` 通过
- 发布配置：通过
- Secret scan：通过，扫描 303 个候选文件
- 当前 `miniprogram/dist`：约 `0.75 MiB`

## 3. 最大后端文件 Top 20

| 文件 | Bytes |
| --- | ---: |
| `backend/main.py` | 60,945 |
| `backend/crud.py` | 34,357 |
| `backend/realtime.py` | 32,660 |
| `backend/models.py` | 26,225 |
| `backend/schemas.py` | 18,903 |
| `backend/tests/test_api.py` | 15,158 |
| `backend/flight_service.py` | 13,656 |
| `backend/flight.py` | 10,634 |
| `backend/games/chess/engine.py` | 10,557 |
| `backend/tests/test_v25_game_api.py` | 10,404 |
| `backend/games/core/state.py` | 10,063 |
| `backend/chess_service.py` | 9,687 |
| `backend/seed.py` | 9,674 |
| `backend/gomoku.py` | 9,502 |
| `backend/games/animal/engine.py` | 9,442 |
| `backend/alembic/versions/20260809_07_chess_data_ai.py` | 9,289 |
| `backend/game_maintenance.py` | 8,323 |
| `backend/game_data_service.py` | 8,319 |
| `backend/games/landlord/rule.py` | 8,253 |
| `backend/tests/test_v28_release.py` | 8,148 |

## 4. 最大小程序源码文件 Top 20

| 文件 | Bytes |
| --- | ---: |
| `src/pages/dice/nativeScene.js` | 33,284 |
| `src/pages/dice/index.jsx` | 20,419 |
| `src/api/index.js` | 17,749 |
| `src/pages/dice-online/index.jsx` | 15,759 |
| `src/pages/games/gomoku/index.jsx` | 15,708 |
| `src/pages/games/flight/index.jsx` | 13,358 |
| `src/pages/games/landlord/index.jsx` | 12,424 |
| `src/pages/admin-dishes/index.jsx` | 11,870 |
| `src/pages/admin-stats/index.jsx` | 11,817 |
| `src/pages/games/chess/index.jsx` | 11,175 |
| `src/pages/wheel/index.jsx` | 11,106 |
| `src/pages/games/animal/index.jsx` | 11,028 |
| `src/pages/games/landlord/index.css` | 10,123 |
| `src/pages/admin-orders/index.jsx` | 9,725 |
| `src/pages/dice-online/index.css` | 9,460 |
| `src/pages/dice/index.css` | 9,413 |
| `src/pages/games/gomoku/index.css` | 9,394 |
| `src/pages/couple/index.css` | 9,349 |
| `src/pages/index/index.jsx` | 8,781 |
| `src/pages/games/index.jsx` | 8,264 |

## 5. HTTP 与 WebSocket 接口

基线共有 85 个 `/api` HTTP route 和 3 个 WebSocket route。

```text
GET /api/health
GET /api/ready
POST /api/customers/session
POST /api/customers/claim-legacy
POST /api/customers/refresh
POST /api/admin/login
GET /api/users/me
PUT /api/users/me
POST /api/users/presence
GET /api/notifications
GET /api/notifications/unread-count
PATCH /api/notifications/{notification_id}/read
GET,POST /api/couple/memories
DELETE /api/couple/memories/{memory_id}
GET,POST /api/couple/dates
DELETE /api/couple/dates/{date_id}
GET /api/couple/profile
GET /api/couple/statistics
GET /api/admin/dashboard
GET /api/games
GET /api/games/records/my
GET /api/games/active
POST /api/games/reconnect/token
POST /api/games/reconnect
GET /api/games/records/{record_id}/replay
GET /api/admin/games/stats
POST /api/games/rooms
GET /api/games/rooms/{room_code}
POST /api/games/flight/create
POST /api/games/flight/join
GET /api/games/flight/{room_code}/state
POST /api/games/flight/action
POST /api/games/landlord/create
POST /api/games/landlord/join
POST /api/games/landlord/action
POST /api/games/animal/create
POST /api/games/animal/join
POST /api/games/animal/move
POST /api/games/chess/create
POST /api/games/chess/join
POST /api/games/chess/move
GET /api/games/chess/{room_code}/state
GET /api/games/chess/{game_id}/history
POST /api/games/{game_type}/ai/move
GET /api/games/ai/players
GET /api/games/ranking
GET /api/games/memories/my
GET /api/games/ai/summary
GET /api/games/{room_code}/state
GET /api/games/achievements
GET /api/games/tasks/my
POST /api/games/tasks/{task_id}/complete
POST /api/games/dice/rooms
POST /api/upload/image
GET,POST /api/dishes
GET,PUT,DELETE /api/dishes/{dish_id}
GET /api/favorites
POST,DELETE /api/favorites/{dish_id}
POST,GET /api/orders
POST /api/orders/{order_id}/repeat-preview
POST /api/orders/repeat/{order_id}
GET /api/admin/orders
GET /api/orders/me
GET /api/orders/my/{legacy_customer_id}
GET /api/orders/{order_id}
PATCH /api/orders/{order_id}/status
POST /api/admin/orders/{order_id}/rollback
POST,GET /api/orders/{order_id}/review
GET /api/couple/score
GET /api/couple/score/history
GET /api/couple/tasks/today
POST /api/couple/tasks/{task_id}/complete
POST /api/couple/score/add
GET /api/stats/favorite-ranking
GET /api/stats/summary
GET /api/stats/dishes
GET /api/stats/recent

WS /ws/admin/orders
WS /ws/game/{room_code}
WS /ws/games/dice/{room_code}
```

## 6. 数据表

当前 SQLAlchemy metadata 包含 32 张表：

```text
achievements, ai_players, chess_games, chess_moves, couple_dates,
couple_memories, customers, daily_tasks, dishes, favorite_dishes,
game_actions, game_event_logs, game_events, game_memories, game_players,
game_reconnect_tokens, game_records, game_replays, game_rooms, game_sessions,
game_states, game_statistics, games, love_scores, love_tasks, notifications,
order_items, order_status_events, orders, reviews, user_achievements, users
```

生产 Schema 以 Alembic 为准；development/test 仍调用 `create_all()` 和 `ensure_compatible_schema()` 兼容旧 SQLite。

## 7. 小程序包结构

- 页面：31
- 主 Tab 页面：5
- `subPackages`：0
- 当前所有页面都进入主包；游戏、管理端、详情和历史页尚未拆包。
- `src/api/index.js` 同时承担 HTTP client、身份、点菜、游戏、情侣与管理接口。

## 8. 依赖

### 后端锁定依赖

```text
fastapi 0.115.12
uvicorn 0.34.2
SQLAlchemy 2.0.40
pydantic 2.11.4
python-multipart 0.0.20
psycopg2-binary 2.9.10
python-dotenv 1.1.0
alembic 1.14.1
redis 5.2.1
Pillow 11.3.0
boto3 1.40.3
httpx 0.28.1 (dev)
pytest 8.3.5 (dev)
```

### 小程序主要依赖

```text
Taro 4.2.x
React / React DOM 18.3.x
Webpack 5.91.x
miniprogram-automator 0.12.x
```

## 9. 环境变量与部署拓扑

当前环境变量：

```text
DATABASE_URL, FRONTEND_URL,
ADMIN_PASSWORD, ADMIN_INVITE_CODE, ADMIN_SECRET, ADMIN_TOKEN_VERSION,
CUSTOMER_INVITE_CODE, ALLOW_LEGACY_CUSTOMER_HEADER, APP_ENV,
UPLOAD_PROVIDER, S3_ENDPOINT, S3_REGION, S3_BUCKET,
S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_PUBLIC_BASE_URL,
REDIS_URL, GAME_ROOM_LEASE_SECONDS, GAME_INSTANCE_ID,
DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_POOL_RECYCLE
```

部署链路：微信小程序 → Render FastAPI/WSS → Neon PostgreSQL；Redis 为可选协调/热缓存；S3-compatible 为目标图片存储。Render 启动前执行 `alembic upgrade head`。

## 10. 当前 Legacy Compatibility

- `gf_customer_id` 是旧浏览器/小程序设备身份，首次认领会把订单、收藏、积分、任务和游戏归属原地迁移到新 customer id。
- `ALLOW_LEGACY_CUSTOMER_HEADER=true` 仅用于 development/test 兼容；生产配置为 false。
- `customers.token_hash` 只保存 opaque bearer token 的 SHA-256 hash。
- `claim-legacy` 对已经认领的 legacy id 返回 409。
- 小程序 401 后删除 bearer token 和 authenticated customer id，但保留 `gf_customer_id`。
- Customer token 没有有效期；refresh 会旋转 token 并立即使旧 token 失效。

## 11. 风险分级

### P0

1. 已认领 legacy identity 丢失 token 后，小程序再次调用 `claim-legacy` 得到 409，无法恢复原历史身份。
2. Customer token 永久有效，缺少到期、显式撤销和恢复治理。
3. 普通邀请码缺失时回退管理员邀请码，未 fail closed。

### P1

1. `main.py`、`crud.py`、`realtime.py` 和小程序 `api/index.js` 已成为高复杂度单文件。
2. Redis 降级到内存限流缺少 readiness 可见性；多实例安全能力会静默变弱。
3. Web 进程内周期任务在多实例下可能重复执行。
4. 金额仍为 Float，时间字段混用 naive/aware datetime。
5. Alembic 与 `ensure_compatible_schema()` 双轨迁移。
6. 长期历史 API 分页不一致，小程序没有 subPackages。

### P2

1. 前端缺少 ESLint、formatter、纯 JS 单元测试和 coverage baseline。
2. CI 缺少 PostgreSQL integration、Ruff、dependency audit 和包体报告。
3. 当前事实与版本专项文档边界不够清晰。

## 12. Phase 1 变更边界

Phase 1 只处理 customer session recovery、邀请码隔离、会话有效期/轮换/撤销、限流、兼容迁移、前端恢复和相关测试。不会拆分 `main.py`、不会修改金额/时间体系、不会拆分小程序分包、不会增加游戏。
