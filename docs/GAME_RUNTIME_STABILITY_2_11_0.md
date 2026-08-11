# 2.11.0 游戏运行时稳定化

## 目标

本版本不增加新游戏，专门补齐多人和长时间运行所需的五个稳定性边界：房间唯一归属、异常结算补偿、过期房间回收、动作幂等，以及斗兽棋/中国象棋的超时与和棋。

## 多实例 WebSocket 房间归属

- `game_rooms.owner_instance_id/lease_expires_at/lease_epoch` 保存当前写入实例的租约。
- WebSocket 实例在接管房间前执行数据库 compare-and-set；30 秒租约由活动实例每 10 秒续期。
- 非归属实例返回 `room_busy` 并关闭连接，现有客户端按指数退避和抖动重连。
- 进程退出或租约过期后，其他实例可接管并从 PostgreSQL `game_states` 恢复大话骰或五子棋。
- PostgreSQL 是正确性边界；Redis 只是可选热缓存。连接切换可能出现一次短暂重连，不宣称跨实例无感迁移。

## 异常结算补偿

- `game_records` 增加 `settlement_status`、`settlement_attempts`、`settlement_error`、`settled_at`。
- 结算先保存完成记录，再以记录 ID 作为奖励、任务、成就、回忆、回放和通知的幂等来源。
- 后台每 60 秒扫描 `pending/failed` 记录；进程在结算中途退出时可继续补齐。
- 同一扫描还会查找已经结束但缺少记录的 `game_sessions/game_states`，创建记录后再结算。
- 单条记录最多自动尝试 10 次，持续失败保留错误文本，便于管理和排障。

## 幽灵房间与生命周期

- `waiting` 房间默认 30 分钟有效，`playing` 房间默认 6 小时有效。
- 创建、加入和成功动作会刷新活动时间及过期时间。
- 过期房间进入 `abandoned`，设置 `abandoned_at/finished_at`，清除租约并撤销重连凭据。
- 不删除 `game_rooms`、玩家、动作或历史记录，审计与统计仍可追踪。

## 动作幂等

- 新增 `game_actions`，唯一键为 `(room_id, player_id, client_action_id)`。
- 飞行棋、斗地主、斗兽棋和中国象棋动作默认由小程序生成 `client_action_id`。
- 同一 ID、同一请求重复到达时返回第一次保存的状态，不重复移动、发奖励或推进轮次。
- 同一 ID 携带不同动作内容时返回 409。
- `expected_version` 继续保护并发写入，飞行棋本版本也加入版本校验。
- 旧客户端不传 `client_action_id` 仍可运行，但没有传输级重复提交保护。

## 斗兽棋与中国象棋规则收口

两款游戏统一增加：

- 每回合 5 分钟；到期后当前玩家超时负。
- 同一局面出现三次自动和棋。
- 斗兽棋连续 100 步无吃子、象棋连续 120 步无吃子或兵卒推进自动和棋。
- 300 步仍未结束自动和棋。
- 服务端状态返回 `result_reason/draw_reason/timed_out_player_id` 和下一回合截止时间。
- 页面区分超时、重复局面、无进展和最大步数，不再把和棋误显示为对方获胜。

## 数据库迁移

迁移：`20260811_10_game_runtime_stability.py`

只做增量修改：

- `game_rooms` 增加租约与放弃时间字段。
- `game_records` 增加结算状态字段。
- 新增 `game_actions`。
- 旧完成记录回填为 `complete`，不删除或重建现有数据。

已验证：空 SQLite 数据库升级到 head、降到 `20260809_09`、再次升级到 head 均成功。生产仍通过启动命令中的 `alembic upgrade head` 升级 PostgreSQL。

## 验证

- 后端全量测试：`70 passed`。
- 新增回归覆盖：租约互斥与过期接管、房间放弃但不删除、重复动作只执行一次、异常结算补偿不重复奖励、斗兽棋/象棋超时与三次重复和棋。
- 小程序脚本覆盖：游戏恢复、离线队列、Socket 重连生命周期与斗地主横屏配置。
- 小程序生产构建：`npm run build:weapp`。

自动化通过不等于已经完成生产多实例流量和两台真机验收。正式发布前仍需在 Render 实际实例和微信真机上执行断网、切后台、重连、同时操作和长局超时验收。
