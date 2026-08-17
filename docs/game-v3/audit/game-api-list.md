# LoveOS V3 游戏 API 清单

审计日期：2026-08-17

## 兼容基线

- 当前 `/api/*` HTTP method/path：89；
- 连同 `GET /` 的业务 HTTP：90；
- WebSocket：3；
- V2 的 88 个 `/api/*` 操作完整保留，V3 仅增加 `GET /api/bootstrap`。

完整全域清单位于 `docs/v3-migration/api-inventory.md`，本文件聚焦游戏中心。

## 通用游戏 API

| Method | Path | 职责 |
| --- | --- | --- |
| GET | `/api/games` | 游戏目录 |
| GET | `/api/games/records/my` | 我的战绩 |
| GET | `/api/games/records/{record_id}/replay` | 成员授权回放 |
| GET | `/api/games/active` | 可恢复房间 |
| POST | `/api/games/reconnect/token` | 签发重连凭证 |
| POST | `/api/games/reconnect` | 恢复权威状态 |
| POST | `/api/games/rooms` | 创建实时房间 |
| GET | `/api/games/rooms/{room_code}` | 房间元数据 |
| GET | `/api/games/{room_code}/state` | 兼容状态读取 |
| POST | `/api/games/{game_type}/ai/move` | 统一本地 AI 动作 |
| GET | `/api/games/ai/players` | AI 人设 |
| GET | `/api/games/ranking` | 排名 |
| GET | `/api/games/achievements` | 成就 |
| GET | `/api/games/tasks/my` | 游戏任务 |
| POST | `/api/games/tasks/{task_id}/complete` | 完成任务 |
| GET | `/api/games/memories/my` | 游戏回忆 |
| GET | `/api/games/ai/summary` | AI 对局摘要 |

## 旧游戏兼容 API

- 飞行棋：`/api/games/flight/create|join|action`、`/api/games/flight/{room_code}/state`；
- 斗地主：`/api/games/landlord/create|join|action`；
- 斗兽棋：`/api/games/animal/create|join|move`；
- 中国象棋：`/api/games/chess/create|join|move`、状态与历史；
- 大话骰：`POST /api/games/dice/rooms`。

这些路径由 adapter 保留，未重命名、删除或改变响应模型。

## WebSocket

| Path | 状态 |
| --- | --- |
| `/ws/game/{room_code}` | 统一 V2 游戏 envelope，骰子/五子棋生产路径 |
| `/ws/games/dice/{room_code}` | 骰子 legacy compatibility |
| `/ws/admin/orders` | 非游戏管理通知，保持不变 |

统一消息继续使用 `type`、`game`、`room_code`、`data`，本轮未改变字段或首帧行为。
