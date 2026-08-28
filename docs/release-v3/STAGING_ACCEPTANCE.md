# LoveOS V3 Staging 验收记录

更新日期：2026-08-28

## 状态

**IN PROGRESS — HOSTED READINESS PASS / WECHAT REAL DEVICE PENDING**

## 隔离前置审计

| 检查 | 状态 | 证据 |
| --- | --- | --- |
| 免费计划 | PASS | Neon 与 Render 控制台均显示 Free；Render 明示空闲休眠 |
| 独立 staging 数据库/分支 | PASS | 新建 Neon 项目 `loveos-staging-release-00`，AWS 新加坡、PostgreSQL 18；创建时存储为 0，不含生产业务数据 |
| 独立 staging API Origin | PASS | `https://girlfriend-menu-api-staging.onrender.com`，与生产 Origin 不同 |
| staging 服务 | PASS | Render 服务 `girlfriend-menu-api-staging` 首次部署成功，来源 `d11a708`，健康检查持续 200 |
| 生产库复用防线 | PASS | 只读门拒绝 production Origin；hosted readiness 确认数据库为 PostgreSQL，未使用生产 API Origin |

## 待执行验收

- [x] 创建免费、独立、无生产业务数据的 Neon staging 项目/数据库。
- [x] 仅在 Render staging Secret 配置独立 `DATABASE_URL` 与 staging 认证 Secret。
- [x] 部署 PR #21 的冻结候选 `d11a708`；启动快路径完成迁移/参考数据检查。
- [x] `/api/health` 返回 200 且标识 LoveOS API。
- [x] `/api/ready` 返回 `status=ready`、`database=postgresql`、持久化存储 ready、认证 ready。
- [x] 在微信关闭状态通过只读门；`wechat_login=optional-disabled` 符合第一阶段策略。
- [ ] 配置真实微信凭据并用 `--require-wechat` 复核。
- [ ] 新用户、存量绑定、换机恢复、管理登录、点单、状态流转、撤回、评价、图片、游戏、WebSocket 全链路通过。
- [x] staging 小程序构建完成，`dist/app.json` 存在，产物完整性检查通过且 API Origin 指向独立 Render staging。
- [ ] 微信开发者工具使用本轮 staging 产物普通启动，红色应用错误为 0。
- [ ] 微信真机覆盖冷启动、弱网、断网重连及核心业务。

## 证据边界

2026-08-28 的 hosted 只读门返回：`database=postgresql`、`storage=ready`、`authentication=ready`、`redis=optional-disabled`、`wechat_login=optional-disabled`。无凭据访问 `/api/bootstrap` 返回 401，符合设备邀请码/会话边界。随后使用 staging 环境构建微信小程序，`dist/app.json` 与 71 个 JavaScript 产物生成成功，140 个模块通过完整性检查，编译产物包含独立 staging API Origin。

此前微信开发者工具普通启动已观察到应用红色错误为 0；自动化连接偶发超时，仅能记录为 `APPLICATION PASS / AUTOMATOR INFRASTRUCTURE UNSTABLE`。这仍不是微信真机证据，带邀请码的业务写链路和微信真机门禁保持未通过状态。
