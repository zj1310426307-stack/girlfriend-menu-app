# LoveOS V3 Staging 验收记录

更新日期：2026-08-28

## 状态

**BLOCKED — ISOLATED STAGING DATABASE NOT PRESENT**

## 隔离前置审计

| 检查 | 状态 | 证据 |
| --- | --- | --- |
| 免费计划 | PASS | Neon 控制台显示 Free |
| 独立 staging 数据库/分支 | BLOCKED | 当前 1 个项目、Branches=1 |
| 独立 staging API Origin | BLOCKED | `.env.staging` Origin 为空 |
| staging Blueprint | PASS | `render.staging.yaml` 为独立免费服务且 `autoDeploy=false` |
| 生产库复用防线 | PASS | 只读门会拒绝 production Origin；本轮未把生产 URL 用作 staging |

## 待执行验收

- [ ] 创建免费、独立、无生产业务数据的 Neon staging 分支/数据库。
- [ ] 仅在 Render staging Secret 配置独立 `DATABASE_URL` 与认证/微信 Secret。
- [ ] 部署 PR #21 的冻结候选，执行 `alembic upgrade head`。
- [ ] `/api/health` 返回 200 且标识 LoveOS API。
- [ ] `/api/ready` 返回 `status=ready`、`database=postgresql`、持久化存储 ready。
- [ ] 先在微信关闭状态通过只读门，再启用真实微信凭据并用 `--require-wechat` 复核。
- [ ] 新用户、存量绑定、换机恢复、管理登录、点单、状态流转、撤回、评价、图片、游戏、WebSocket 全链路通过。
- [ ] staging 构建和微信开发者工具普通启动红色错误为 0。
- [ ] 微信真机覆盖冷启动、弱网、断网重连及核心业务。

## 证据边界

此前微信开发者工具普通启动已观察到应用红色错误为 0；自动化连接偶发超时，仅能记录为 `APPLICATION PASS / AUTOMATOR INFRASTRUCTURE UNSTABLE`。这不是 staging hosted 验收，也不是微信真机证据。
