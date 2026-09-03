# Continuous Optimization 02 兼容与迁移说明

- 日期：2026-08-24
- 范围：认证 readiness、密码 verifier 可用性、运行日志隐私
- 数据库 revision：保持 `20260817_14`

## 1. 兼容结论

| 边界 | 结论 | 说明 |
| --- | --- | --- |
| 业务 HTTP API | 完全兼容 | 路由、method、DTO、状态码、bearer 和业务响应不变 |
| `/api/ready` | 加法兼容 | 保留 HTTP 200 和原字段；新增 `authentication`，总状态增加认证 blocker |
| OpenAPI | 无变化 | readiness 仍为 `include_in_schema=False`，快照检查通过 |
| WebSocket | 完全兼容 | 路由、envelope、close code、重连和结算行为不变 |
| 数据库 | 完全兼容 | 无表、列、索引、约束、数据迁移或新 Alembic revision |
| 小程序 | 完全兼容 | 源码、页面、分包、本地存储和 API 调用均未修改 |
| 运维日志 | 有意收紧 | 原始 path/key/room/request id 改为 route template 或进程内短引用 |

## 2. Authentication readiness

`/api/ready.authentication` 的结构为：

```json
{
  "status": "ready | release-blocked",
  "missing": ["仅包含安全的配置项名称"]
}
```

判定规则：

- 始终要求 `CUSTOMER_INVITE_CODE`、`ADMIN_INVITE_CODE` 和长度至少 16 的 `ADMIN_SECRET`。
- 没有数据库管理员账号时，需要 `ADMIN_PASSWORD`，或由项目脚本生成且结构有效的 `ADMIN_PASSWORD_HASH`。
- 已有启用的数据库管理员账号时，以数据库 verifier 为权威，不要求继续保留 bootstrap password。
- 已有账号但被禁用或 verifier 损坏时阻止发布；环境变量不能绕过禁用状态。
- `APP_ENV=staging|production` 时，客户与管理员邀请码必须不同；development/test 保留原兼容行为。

新增 blocker 只改变发布判定，不关闭服务，也不改变登录接口的 HTTP 语义。readiness 不返回配置值、散列或数据库异常详情。

## 3. 密码 verifier 兼容

密码验证现在显式接受本项目一直生成的固定 scrypt 格式：`N=16384`、`r=8`、`p=1`、16-byte salt、32-byte digest。由 `scripts/hash_admin_password.py`、管理账号 bootstrap 或密码轮换生成的历史值无需迁移。

若曾手工拼装不同长度的 scrypt 字符串，它可能在旧代码中被尝试验证，本轮会 fail closed，并在 readiness 中显示：

- `ADMIN_PASSWORD_HASH`：尚无数据库账号，环境 bootstrap hash 无效；
- `ADMIN_ACCOUNT_PASSWORD_HASH`：数据库账号 verifier 无效。

修复方式是用项目脚本重新生成环境 hash，并通过一次完整的管理登录轮换；不要直接在生产库写明文密码或跳过邀请码。

## 4. 日志字段迁移

| 旧字段/行为 | 新字段/行为 |
| --- | --- |
| HTTP `id=<raw request id>` | `request_ref=request:<12 hex>` |
| HTTP `path=<dynamic path>` | `route=<framework route template>` |
| 未匹配 path 原文 | `route=/unmatched` |
| Redis key 原文 | `key_ref=cache-key:<12 hex>` |
| room code 原文 | `room_ref=room:<12 hex>` |
| 隐私敏感 traceback/异常消息 | `error_type=<class name>` |
| Uvicorn 原始 access log | 标准 `serve.py` 中关闭 |

短引用使用随机的进程内 HMAC key。同一进程内相同输入得到相同引用，便于短期排障；进程重启或实例切换后引用会变化，不能作为持久指标、业务主键或跨实例 trace id。现有日志查询和告警若依赖 `path`、`id` 或 `room` 字段，需要在发布前改用 `route`、`request_ref` 和 `room_ref`。

`X-Request-Id` 响应头仍按原行为回传，不影响客户端排障协议；只是日志不再保存其原文。

## 5. 数据库与客户端迁移

本轮无数据库迁移、数据回填或客户端 storage 迁移。部署仍执行现有 Alembic 链到 `20260817_14`，只是为了验证候选与既有数据库兼容。小程序无需配套版本即可继续使用旧后端或新后端。

## 6. 发布顺序

1. 在隔离免费 staging 部署候选，使用独立数据库与独立 secrets。
2. 执行现有 Alembic 链，确认 head 为 `20260817_14`。
3. 配置分离的客户/管理员邀请码、有效 `ADMIN_SECRET` 和管理密码/hash。
4. 检查 `/api/ready` 的 `authentication.status=ready` 且 `missing=[]`。
5. 若开启微信登录，再检查 `wechat_login.status=ready`；存储必须为 ready。
6. 确认日志只有 route template/短引用，没有动态 URL、房间码或 cache key 原文。
7. 完成微信 DevTools、体验版和真机登录、下单、管理与在线游戏验收后，才允许人工生产发布。

## 7. 回滚

- 应用回滚：回退第二轮代码提交即可；无需 Alembic downgrade 或数据恢复。
- readiness 回滚：旧版会忽略新增聚合规则，但不建议在认证 blocker 未修复时强行发布。
- 日志回滚：仪表盘可临时同时接受旧/新字段；不建议恢复原始动态 URL、key、room code 或 traceback。
- verifier 回滚：若历史手工 hash 被新校验拒绝，应前滚重新生成标准 hash；回退校验仅作为短期应急且必须保留访问控制。

## 8. 外部未验证项

本地 SQLite、TestClient 和本地 Uvicorn 不能替代 PostgreSQL staging、Render 日志窗口、微信体验版或真机弱网证据。本轮未部署外部环境、未使用付费服务、未修改生产数据。
