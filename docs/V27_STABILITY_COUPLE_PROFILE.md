# V2.7 系统稳定化与情侣档案

## 架构边界

V2.7 没有更换 FastAPI、SQLAlchemy、Taro 或 PostgreSQL，也没有增加新游戏。新增能力按职责放入独立服务：

- `user_service.py`：把既有 `customer_id`、管理员和 AI 编码映射到统一 `users`，旧标识不变。
- `notification_service.py`：订单、游戏和纪念日站内通知。
- `couple_profile_service.py`：共同记忆、纪念日、情侣主页与跨域统计。
- `game_recovery_service.py`：哈希重连凭证、未完成房间、通用回放。
- `core/cache.py`：可选 Redis 热状态与在线 TTL；失败时不阻断 PostgreSQL 业务。
- `system_stats_service.py`：管理驾驶舱只读聚合。

PostgreSQL 始终是持久事实来源。Redis 只保存七天游戏热快照和 90 秒在线标记；`REDIS_URL` 留空时，点餐、档案、持久游戏和管理端仍可工作。大话骰和五子棋若希望跨后端进程恢复正在进行的局面，需要配置 Redis。

## 数据库迁移

迁移 `20260809_08` 只新增以下表，不改写旧订单或旧 `customer_id`：

- `users`
- `notifications`
- `couple_memories`
- `couple_dates`
- `game_reconnect_tokens`
- `game_replays`

重连令牌的原文只在签发时返回给当前设备；数据库只保存 SHA-256 哈希和过期时间。

## 新增 API

所有普通用户接口继续使用 `X-Customer-Id`：

- `GET/PUT /api/users/me`
- `POST /api/users/presence`
- `GET /api/notifications`
- `GET /api/notifications/unread-count`
- `PATCH /api/notifications/{id}/read`
- `GET/POST/DELETE /api/couple/memories`
- `GET/POST/DELETE /api/couple/dates`
- `GET /api/couple/profile`
- `GET /api/couple/statistics`
- `GET /api/games/active`
- `POST /api/games/reconnect/token`
- `POST /api/games/reconnect`
- `GET /api/games/records/{id}/replay`
- `GET /api/admin/dashboard`（管理员 Bearer token）

## 自动事件

- 第一次提交订单：写入 `FIRST_MEAL`，管理端收到新订单通知。
- 订单状态变化：用户收到进度通知；第一次完成写入 `FIRST_COOK`。
- 评价：管理端收到评价通知。
- 第二位玩家加入：房主和加入者收到游戏通知。
- 游戏结算：参与者收到完成通知，生成时间轴记录和通用回放。
- 请求消息或情侣主页时：幂等生成临近纪念日提醒。
- 后端常驻进程每 6 小时补跑一次纪念日提醒；Render 休眠时仍由用户下一次打开页面触发补偿。

## 小程序页面

- `pages/couple/timeline`：时间轴、手写共同记录、纪念日与提前提醒。
- `pages/notifications/index`：订单、游戏和纪念日消息。
- “我们”主页：相处天数、共同记录、下个纪念日和未读数。
- 游戏大厅：展示可继续的未完成房间。
- 管理统计：今日订单、游戏、积分、热门菜和热门游戏驾驶舱。

## 部署配置

新增可选变量：

```text
REDIS_URL=
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
```

Render 可绑定 Redis/Key Value 提供的内部 URL。未配置 Redis 时 `/api/ready` 会返回 `redis: optional-disabled`，这是正常降级而不是故障。

## 验证基线

- `pytest -q`：47 项通过。
- Alembic：全新数据库升级到 `20260809_08`、降级到 `20260809_07`、再升级成功。
- `npm run build:weapp`：生产构建通过。
- 微信开发者工具：`npm run test:v27` 覆盖情侣主页、时间轴、通知与游戏大厅。
