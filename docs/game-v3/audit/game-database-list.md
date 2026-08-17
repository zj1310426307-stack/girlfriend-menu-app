# LoveOS V3 游戏数据库清单

审计日期：2026-08-17

## 统一核心表

| 表 | 职责 |
| --- | --- |
| `games` | 游戏目录 |
| `game_rooms` | 房间元数据、状态版本、租约和过期策略 |
| `game_players` | 房间座位、分数、断线窗口 |
| `game_states` | 实时房间 JSON/JSONB 快照 |
| `game_sessions` | 回合制游戏版本化权威状态 |
| `game_actions` | 幂等动作回执与版本 CAS |
| `game_records` | 每房间/局唯一战绩与结算状态 |
| `game_replays` | 通用动作序列和最终状态 |
| `game_reconnect_tokens` | 哈希后的长期重连凭证 |
| `game_events` / `game_event_logs` | 情侣互动事件与防重复完成日志 |

成就、任务、统计、回忆和默契积分继续使用现有跨游戏表，不迁移、不丢失。

## 游戏专用兼容表

`chess_games` 和 `chess_moves` 仍被中国象棋历史/回放兼容路径引用。删除前必须取得生产读写追踪、完成数据回填并经过双读校验；当前没有证据满足条件，因此保留。

## Schema 状态

- Alembic head：`20260817_13`；
- `game_states.state`、`game_sessions.state`、`game_records.result`、`game_replays.moves/final_state` 等 PostgreSQL 目标已使用 JSONB variant；
- SQLite 测试继续使用 JSON，保持本地隔离测试兼容。

## 决策

共享对话提出的统一 session/record/move 目标已由现有表覆盖。此时再创建同义表或立即删除专用表会增加双写、回滚和数据丢失风险。本轮数据库变更为 0，所有迁移文件原样保留。
