# LoveOS V3 游戏数据库变更报告

## 结果

本轮新增表 0、删除表 0、修改列 0、迁移文件 0。Alembic head 保持 `20260817_13`。

## 原因

现有 Schema 已有统一的 rooms、players、states、sessions、actions、records、replays、reconnect tokens 和 event logs。立即再建 `game_moves` 或删除象棋专用表会造成同义数据源、双写与不可证明的数据丢失。

## 保留的数据能力

- 每房间/局唯一战绩；
- JSONB 生产状态和回放；
- action idempotency 与 expected version；
- pending settlement 可重试；
- 排名、成就、任务、回忆、默契积分；
- 30 分钟等待房、6 小时进行中房、60 秒断线座位窗口；
- 成员授权回放与哈希重连 token。

## 删除专用表的未来门槛

必须先完成生产读写追踪、数据回填、双读对账、回滚备份和至少一个发布周期的零读写证据。当前未满足，因此保留所有历史迁移。
