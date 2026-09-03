# LoveOS V3 数据库迁移报告

验证日期：2026-08-17
V2 head：`20260812_12`
V3 head：`20260817_13`

## 结论

现有 34 张生产表和完整 Alembic 历史全部保留，没有压扁迁移、删表、改主键或重命名公开字段。新增 revision 只在 PostgreSQL 把剩余可扩展载荷 `dishes.tags` 与 `game_records.result` 从 JSON 转为 JSONB；SQLite 保持兼容 no-op。

## 迁移内容

- `models.py` 使用 `JSON().with_variant(JSONB, "postgresql")`，SQLite 测试仍使用 JSON。
- `20260817_13_v3_jsonb_targets.py` 使用 PostgreSQL 显式 `USING column::jsonb` 升级。
- downgrade 使用 `USING column::json`，具备单步回滚路径。
- `database/v3-schema.sql` 是 PostgreSQL 目标 DDL 快照，不替代 Alembic 真相源，也不包含破坏性 `DROP TABLE`。

## 验证结果

| 验证 | 结果 |
| --- | --- |
| 单一 Alembic head | PASS：`20260817_13` |
| 隔离空 SQLite：`upgrade head` | PASS |
| `downgrade -1` | PASS |
| 再次 `upgrade head` | PASS |
| SQLAlchemy 元数据与 V3 schema 快照 | PASS |
| 完整 pytest | PASS：182 passed |
| 默认开发数据库未被 pytest 修改 | PASS，由隔离护栏检查 |

## 数据保留判断

`game_states`、`game_sessions`、象棋专用表及游戏记忆表存在部分概念重叠，但没有生产读写对账证据支持安全合并。本轮删除表为 0，避免为了得到简短 schema 而破坏恢复、回放或审计能力。

## 风险和发布门槛

- 本地验证覆盖 SQLite 升降级；尚未在 staging PostgreSQL 执行本 revision。
- JSON→JSONB 会取得表锁，生产发布前应在 staging 用生产级数据量记录锁时长和查询计划。
- Python 3.12 的 SQLite datetime adapter 产生 11 条弃用警告，不影响本轮结果，但需后续替换显式适配器。

## 回滚

应用回滚到 V2 前，可先执行 `alembic downgrade 20260812_12`。若生产已大量写入只适用于 JSONB 的值，应优先前向修复并先做备份；本轮应用写入的结构均是标准 JSON，可直接转换。
