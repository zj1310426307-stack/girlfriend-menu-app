# LoveOS V3 数据库审计

审计日期：2026-08-17
Alembic head：`20260812_12`

## 结论

当前数据库不是需要压扁重建的临时结构。12 个 Alembic revision 构成线性历史，34 张表覆盖身份、点菜、情侣、游戏、可恢复会话和图片。V3 不删除迁移历史、不在生产库中重命名核心表，也不把多个具备不同一致性约束的表强行合并成一个 JSON 大表。

提示词给出的 10 张“核心表”只能作为概念域，不能作为实际删表清单。例如当前并不存在独立 `couples` 和 `scores` 表；情侣关系由当前单租户/用户模型与相关表表达，积分由 `love_scores` 和 `game_statistics` 分别承担事件账本和聚合统计。

## 迁移链

```text
20260808_01 -> 20260809_02 -> 20260809_03 -> 20260809_04
-> 20260809_05 -> 20260809_06 -> 20260809_07 -> 20260809_08
-> 20260809_09 -> 20260811_10 -> 20260811_11 -> 20260812_12
```

基线 head 只有一个：`20260812_12`。

## 表级处理清单

| 表 | V3 动作 | 原因 |
| --- | --- | --- |
| `users` | 保留 | 管理员、客户映射和 AI 用户的统一公开身份 |
| `customers` | 保留 | 设备客户身份和旧身份认领 |
| `customer_sessions` | 保留 | 轮换、吊销和过期的安全会话 |
| `dishes` | 保留/扩展 | 菜品核心；未来图片派生信息应另表或可选字段 |
| `favorite_dishes` | 保留 | 客户与菜品多对多，不应塞入 JSON |
| `orders` | 保留 | 订单聚合根、幂等键和状态 |
| `order_items` | 保留 | 下单时快照和数量明细 |
| `order_status_events` | 保留 | 可审计状态历史 |
| `reviews` | 保留 | 订单一对一评价 |
| `love_scores` | 保留 | 积分事件账本，不与统计快照合并 |
| `daily_tasks` | 保留 | 每日任务实例 |
| `couple_dates` | 保留 | 纪念日及提醒规则 |
| `couple_memories` | 保留 | 时间轴与来源引用 |
| `notifications` | 保留 | 持久消息和未读状态 |
| `games` | 保留/迁移语义 | 作为插件目录投影；稳定 `type` 与插件 ID 对齐 |
| `ai_players` | 保留/迁移语义 | 作为 AI 策略配置目录，不存运行时对象 |
| `game_rooms` | 保留 | 房间生命周期、租约和版本 |
| `game_players` | 保留 | 座位、恢复会话和活跃状态 |
| `game_sessions` | 保留 | 当前权威回合状态和乐观版本 |
| `game_states` | 保留/评估合并 | 与 `game_sessions.state` 部分重叠；先完成读写追踪再决定 |
| `game_actions` | 保留 | 动作幂等、请求哈希和响应版本 |
| `game_records` | 保留 | 已统一的跨游戏记录，`result` JSON 提供扩展 |
| `game_replays` | 保留 | 完整动作与最终状态可能较大，不塞回记录行 |
| `game_statistics` | 保留 | 面向查询的聚合，不替代事件记录 |
| `game_reconnect_tokens` | 保留 | 一次性安全恢复凭据 |
| `game_events` | 保留 | LoveOS 随机互动目录 |
| `game_event_logs` | 保留 | 用户完成状态和奖励审计 |
| `game_memories` | 保留/评估合并 | 与情侣记忆有关联但查询、权限和来源不同，暂不合并 |
| `love_tasks` | 保留 | 游戏后情侣约定和幂等奖励 |
| `achievements` | 保留 | 成就规则目录 |
| `user_achievements` | 保留 | 解锁事实和唯一性 |
| `chess_games` | 保留/迁移读取 | 象棋专用检索与着法头信息；先由 adapter 双读验证 |
| `chess_moves` | 保留/迁移读取 | 象棋着法序列；统一回放可引用，不能直接删除 |
| `uploaded_images` | 保留/扩展 | 数据库存图兼容；派生缩略图需保持原资源可用 |

## 分类汇总

- **保留**：全部 34 张现有表，保证生产数据和旧 API。
- **迁移语义**：`games`、`ai_players` 与 V3 注册表对齐，但不改主键和公开字段。
- **评估合并**：`game_states`、`game_memories` 只有在读写路径、数据回填、回滚和性能证据齐全后才进入新 revision。
- **删除**：当前为 0。没有证据支持安全删除任何生产表。

## V3 目标模式文件

`database/v3-schema.sql` 将作为 PostgreSQL 目标结构的可读快照，而不是新的迁移真相源。真实生产升级仍只通过 Alembic 执行。该文件必须：

- 标明生成/审计来源；
- 保留所有生产表；
- 使用 PostgreSQL JSONB 表达可扩展游戏结果/状态；
- 不包含破坏性 `DROP TABLE`；
- 与 Alembic head 的模型元数据做自动核对。

## 风险

1. SQLite 测试与 PostgreSQL 生产的 JSON、datetime、并发行为不同。
2. Python 3.12 已对 SQLite 默认 datetime adapter 发出弃用警告。
3. `models.py` 和 `schemas.py` 较大，拆分时容易产生循环导入或 Alembic 元数据漏表。
4. 直接压扁迁移会让现有数据库失去升级路径，明确禁止。

## 验收

- `alembic heads` 仍只有一个 head。
- 从空库 `upgrade head` 成功。
- 现有数据库升级不丢表、不丢列。
- customer session、订单幂等、游戏动作幂等测试全部通过。
- 模式快照与 SQLAlchemy metadata 表名集合一致。
