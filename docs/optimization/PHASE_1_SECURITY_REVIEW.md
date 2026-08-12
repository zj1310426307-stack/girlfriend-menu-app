# Phase 1 身份与会话安全复盘

> 完成日期：2026-08-11（Asia/Shanghai）
>
> 执行范围：仅完成主任务书 Phase 1；未进入 Phase 2 UI、业务或架构改造。

## 1. 原始风险

Phase 0 基线确认普通端已经使用 Bearer token，但存在以下高优先级缺口：

1. 旧设备的 `gf_customer_id` 一旦已经通过 `claim-legacy` 认领，本地 token 丢失后再次认领会返回 409，用户无法恢复历史订单身份。
2. 客户 token 没有服务端过期、撤销或轮换记录，泄露后的生命周期无法控制。
3. 普通端邀请码在缺少 `CUSTOMER_INVITE_CODE` 时会回退到 `ADMIN_INVITE_CODE`，扩大了管理凭据的暴露面。
4. 旧身份迁移、会话生命周期和数据库升级没有独立回归测试，无法证明旧订单、收藏、积分与游戏记录不丢失。

## 2. 最终设计

本阶段保留 `customers.customer_id` 作为稳定业务身份，不改订单、收藏、积分和游戏记录中的既有归属字段；新增一对多的 `customer_sessions` 作为认证层：

- 原始 token 只返回给客户端一次，数据库仅保存 SHA-256 哈希。
- 每条会话记录 `created_at`、`last_seen_at`、`expires_at`、`revoked_at`、`rotated_from_id` 和可选 `device_label`。
- 默认有效期为 90 天，通过 `CUSTOMER_SESSION_TTL_DAYS` 配置，服务端限制为 1～365 天。
- 刷新会创建新 token、撤销当前 token，并保留轮换来源。
- 主动撤销接口立即使当前 token 失效。
- 身份恢复使用仍保留在本地的旧 `gf_customer_id` 加普通端邀请码；恢复成功后撤销该客户所有旧会话，再签发新 token。
- `claim-legacy` 保持原 409 行为，以兼容旧客户端契约；新客户端统一调用 `/api/customers/recover`。
- 旧 `customers.token_hash` 暂不删除：迁移会回填为有期限会话，运行时也保留一次惰性桥接，便于先部署代码或先运行迁移的灰度顺序。

## 3. 邀请码隔离

普通端认证只读取 `CUSTOMER_INVITE_CODE`。如果未配置则返回 503，不再回退到 `ADMIN_INVITE_CODE`。管理密码、管理邀请码和管理签名密钥继续只服务管理端。

恢复接口按请求 IP 使用现有速率限制器限制为 10 分钟 5 次。邀请码只是私人应用的准入因子，不是微信账号、OpenID、手机号或高强度账号找回凭据。

## 4. API 变化

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST | `/api/customers/session` | 新建客户和有期限设备会话；可提交 `device_label` |
| POST | `/api/customers/claim-legacy` | 兼容旧客户端的一次性认领；重复认领仍为 409 |
| POST | `/api/customers/recover` | 恢复或首次迁移旧身份，撤销旧会话并返回新 token |
| POST | `/api/customers/refresh` | 轮换当前 Bearer token |
| POST | `/api/customers/revoke` | 撤销当前 Bearer token，成功返回 204 |

会话响应增加非空 `expires_at`。原有 Bearer 保护接口路径和业务响应不变。

## 5. 客户端兼容

小程序新增 `gf_customer_expires_at`。启动时如果会话已过期，只清理认证 ID、token 和过期时间，保留旧 `gf_customer_id`，因此用户输入普通端邀请码后仍可恢复原业务身份。

为兼容升级前已经保存在本地、但没有过期时间的 token，客户端不会因为缺失 `gf_customer_expires_at` 立即把它判定为无效；服务端会通过迁移会话或惰性桥接完成验证。

## 6. 数据库迁移

Alembic `20260811_11_customer_sessions`：

- 新增 `customer_sessions` 表、唯一 token 哈希和客户/过期/撤销索引。
- 对旧 `customers.token_hash` 做幂等回填，迁移会话有效期为执行迁移后 90 天。
- 兼容 development/test 中 `create_all` 已提前创建表的情况。
- 不修改或删除旧 `customers`、`orders`、`favorite_dishes`、`love_scores`、`game_players`、`game_records` 数据。
- 降级只删除 `customer_sessions`；`customers.token_hash` 仍在，可在应用回滚后继续验证旧 token。

## 7. 测试结果

- 后端全量：`79 passed`，另有 11 条 Python 3.12 SQLite datetime adapter 弃用警告，不影响结果。
- 会话专项：覆盖创建、过期、撤销、刷新轮换、旧哈希惰性桥接、恢复后业务归属不变、错误邀请码、限流、邀请码隔离和并发首次恢复。
- 迁移专项：SQLite 从前一版本升级、旧 token 回填、降级一版、再次升级均通过。
- 小程序会话契约：`npm run test:session` 通过。
- 既有游戏契约：`npm run test:games`、`npm run test:landlord` 通过。
- 小程序生产构建：`npm run build:weapp` 通过。
- 发布配置检查和 secret scan 通过。

## 8. 数据保护结论

专项测试证明恢复前后的客户主键和 `customer_id` 不变，以下关联数据仍归属于原身份：订单、收藏、情侣积分、游戏席位和游戏记录。迁移不重建任何业务表。

本阶段无法在用户主动清空微信小程序全部本地存储后，仅凭邀请码自动判断其旧身份；这是匿名设备身份模型的固有限制。跨设备、无旧 ID 找回必须在未来接入 OpenID 或明确的账号绑定后实现。

## 9. 生产发布与回滚

推荐顺序：

1. 备份 Neon PostgreSQL。
2. 配置独立 `CUSTOMER_INVITE_CODE` 和 `CUSTOMER_SESSION_TTL_DAYS=90`。
3. 执行 `alembic upgrade head`，确认 head 为 `20260811_11`。
4. 部署后端，再上传小程序；用一个已存在历史订单的设备验证自动恢复、订单列表和刷新。
5. 观察 401、409、429 和 `/api/ready`；确认无异常后再扩大体验范围。

回滚必须先回滚后端应用，再执行 `alembic downgrade -1`。新代码运行期间不得提前删除 `customer_sessions`。因为旧 `customers.token_hash` 保留，应用回滚后旧认证路径仍有数据桥。

## 10. 剩余风险

- 当前是匿名设备会话，不具备微信账号级的跨设备身份保证。
- 恢复操作会撤销同一客户的全部旧会话，符合当前“一位女朋友、单主设备”的私人产品定位；未来支持多设备时需要改成按设备选择性撤销。
- 生产 Neon 的真实迁移、Render 冷启动和微信真机升级路径尚未在本阶段执行。
- S3/R2 凭据与双真机联机验收仍是发布清单中的独立阻断项，不属于本次身份代码变更。

## 11. 是否建议进入 Phase 2

**暂不建议立即进入 Phase 2。** 先把 Phase 1 部署到受控体验环境，完成一次 Neon 备份/迁移和“已有订单设备升级后恢复身份”的真机冒烟；验证通过后，可以在独立变更中进入 Phase 2。这样可以把身份安全变更和后续 UI/业务改造分开回滚。
