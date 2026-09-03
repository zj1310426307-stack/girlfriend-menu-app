# LoveOS V3 Continuous Optimization 01 发布说明

- 候选日期：2026-08-24
- 分支：`feature/continuous-optimization-01`
- 状态：本地候选通过；尚未部署 staging/production，尚未完成微信真机验收
- 费用边界：继续使用免费 Blueprint；本轮未创建付费资源

## 1. 本轮产品结果

### 已登录页面更少数据库写入

客户认证仍逐请求校验数据库中的撤销、过期和账号状态，但 `last_seen_at` 改为 5 分钟服务端节流。热 session 的首页、菜单、订单和其他读取不再因为 activity 字段额外执行两表 UPDATE/commit；stale 并发请求通过条件更新只允许一个 winner。

### 同设备切换账号不再串用私有状态

- reconnect token 由 `customerId + roomCode` 共同拥有。
- 旧无 owner token 不读取，只删除。
- 退出、过期或 owner 变化时清理购物车、复购草稿、客户快照、reconnect 和遗留 room-session secret。
- 同 owner token 刷新继续保留草稿；legacy 设备 ID 和公共菜品缓存保留。
- WebSocket session 事件仍交给页面，但未使用 secret 不再长期落盘。

### 生产发布改为免费人工门

- production/staging/Oregon Blueprint 均保持 `plan: free`。
- production `autoDeploy:false`，代码合并不会自动触发启动迁移。
- `.env.example` 的秘密字段全部留空。
- 生产 API 逻辑备份要求 origin、密码和邀请码显式提供，且只接受 HTTPS。
- 静态发布门检查手动发布、免费计划、弱默认和备份工具默认值。

## 2. 同一分支纳入的既有 V3 候选

本轮开始时工作区已有多轮未提交 V3 生产化改动。为了消除“本机能跑但提交不完整”的发布阻断，本分支在通过全量验证后将它们按逻辑纳入提交，包括：

- 微信身份适配、管理员数据库账号、订单安全和对应 migration/tests。
- V3 bootstrap、首页/Tab local-first snapshot、请求 ownership 和加载反馈。
- `serve.py` 免费启动快路径、staging/Oregon 免费候选、发布/回滚材料。
- OpenAPI/schema 快照和 V3 性能预算。

这不表示外部云端或真机已验收；历史材料仍按其日期保留事实边界。

## 3. 兼容与迁移

- HTTP API、路由、DTO、token 格式：兼容，无本轮合同变化。
- WebSocket 公共消息：兼容；仅删除未被消费的客户端 secret persistence。
- 数据库：本轮无 schema 调整、无新增 migration。
- 前端路由和业务规则：兼容。
- 本地临时数据：会话边界有意清除，详见 `docs/migration/COMPATIBILITY_AND_MIGRATION.md`。
- 生产触发：由自动部署调整为人工发布；运行规格和费用不变。

## 4. 验证摘要

- 后端：236 passed，Ruff、Import Linter、compileall、OpenAPI/schema check 全部通过。
- 小程序：干净 npm 安装、生产 WeApp build、`test:ci` 全部通过。
- 迁移：empty upgrade、down/up、from-V2 upgrade 到 `20260817_14` 全部通过（SQLite）。
- 启动：`serve.py` 启动成功，`/api/health` 返回 200。
- 免费准备路径：本地空 SQLite 1334.6 ms，随后快速路径 3.2 ms。
- 包体：主包 469,038 B，总产物 888,826 B。
- 发布门：配置检查和 487 文件秘密扫描通过。

详细命令、环境、warning 和未验证项见 `docs/verification/OPTIMIZATION_VERIFICATION_REPORT.md`。

## 5. 修改文件清单

以下为相对接管基线 `aedae15594577d5ef883fdd51760749607e9d4c5` 的已修改文件；分组写法中的每个路径都属于实际 diff：

```text
README.md
backend/.env.example
backend/api/routes/auth.py
backend/api/routes/bootstrap.py
backend/api/routes/orders.py
backend/api/routes/system.py
backend/auth.py
backend/core/settings.py
backend/customer_service.py
backend/main.py
backend/models.py
backend/repositories/orders.py
backend/schemas.py
backend/services/bootstrap_service.py
backend/services/order_service.py
backend/services/review_service.py
backend/task_service.py
backend/tests/test_api.py
backend/tests/test_phase2b_round2_contracts.py
backend/tests/test_router_contract.py
backend/tests/test_settings_contracts.py
backend/tests/test_v3_api_compatibility.py
backend/tests/test_v3_bootstrap.py
backend/tests/test_v3_database_schema.py
database/v3-schema.sql
docs/v3-migration/openapi-v3.json
miniprogram/.env.staging
miniprogram/config/index.js
miniprogram/package-lock.json
miniprogram/package.json
miniprogram/scripts/customer-session-contract-test.cjs
miniprogram/scripts/v3-architecture-test.cjs
miniprogram/src/api/gameSocket.js
miniprogram/src/api/index.js
miniprogram/src/api/modules/catalog.js
miniprogram/src/api/transport.js
miniprogram/src/app.config.js
miniprogram/src/components/DishCard.css
miniprogram/src/components/DishCard.jsx
miniprogram/src/config/routes.js
miniprogram/src/pages/admin-orders/index.css
miniprogram/src/pages/admin-orders/index.jsx
miniprogram/src/pages/couple/index.jsx
miniprogram/src/pages/games/index.css
miniprogram/src/pages/games/index.jsx
miniprogram/src/pages/index/index.css
miniprogram/src/pages/index/index.jsx
miniprogram/src/pages/menu/index.jsx
miniprogram/src/pages/my-orders/index.jsx
miniprogram/src/pages/order-detail/index.css
miniprogram/src/pages/order-detail/index.jsx
miniprogram/src/utils/cart.js
miniprogram/src/utils/customer.js
miniprogram/src/utils/gameRecovery.js
miniprogram/src/utils/status.js
render.yaml
scripts/backup_production_api.py
scripts/benchmark_v3.py
scripts/check_release_config.py
scripts/export_openapi.py
scripts/export_v3_schema.py
```

## 6. 新增文件清单

```text
backend/alembic/versions/20260817_14_wechat_identity.py
backend/integrations/__init__.py
backend/integrations/wechat.py
backend/release.py
backend/serve.py
backend/services/admin_auth_service.py
backend/services/free_runtime_service.py
backend/services/startup_service.py
backend/services/wechat_auth_service.py
backend/tests/test_admin_auth_hardening.py
backend/tests/test_customer_activity_throttle.py
backend/tests/test_order_mutation_safety.py
backend/tests/test_order_submission_safety.py
backend/tests/test_startup_release.py
backend/tests/test_wechat_integration.py
backend/tests/test_wechat_login.py
docs/THREAD_HANDOFF_2026-08-13.md
docs/THREAD_HANDOFF_2026-08-18.md
docs/audit/CURRENT_STATE_AUDIT.md
docs/audit/OPTIMIZATION_BACKLOG.md
docs/migration/COMPATIBILITY_AND_MIGRATION.md
docs/optimization/PHASE_3_1_A_HOSTED_LATENCY_REPORT.md
docs/optimization/PHASE_3_1_A_HOSTED_TEST_PLAN.md
docs/optimization/V3_PRODUCT_REVIEW_2026-08-20.md
docs/plan/OPTIMIZATION_EXECUTION_PLAN.md
docs/release/OPTIMIZATION_RELEASE_NOTES.md
docs/release-v3/README.md
docs/release-v3/architecture.md
docs/release-v3/deployment.md
docs/release-v3/final-report.md
docs/release-v3/monitoring.md
docs/release-v3/performance-rollout-plan.md
docs/release-v3/test-report.md
docs/release-v3/wechat-release-checklist.md
docs/verification/OPTIMIZATION_VERIFICATION_REPORT.md
miniprogram/scripts/home-launch-performance-contract-test.cjs
miniprogram/scripts/product-core-flow-test.cjs
miniprogram/scripts/session-owned-storage-behavior-test.cjs
miniprogram/scripts/tab-launch-performance-contract-test.cjs
miniprogram/src/components/PageSyncNotice.css
miniprogram/src/components/PageSyncNotice.jsx
miniprogram/src/utils/homeSnapshot.js
miniprogram/src/utils/pageSnapshot.js
miniprogram/src/utils/sessionOwnedStorage.js
render.production-oregon.yaml
render.staging.yaml
scripts/hash_admin_password.py
```

## 7. 删除文件

无。本轮没有删除现有文件或正常功能。

## 8. 部署步骤

### 本地后端

```powershell
cd D:\my-project\girlfriend-menu-app\backend
Copy-Item .env.example .env
# 显式填写本地邀请码和管理秘密，不能恢复仓库已移除的弱默认。
.\.venv\Scripts\python.exe serve.py
```

### 小程序候选

```powershell
cd D:\my-project\girlfriend-menu-app\miniprogram
npm ci
npm run test:ci
npm run build:weapp
```

### 生产

1. 推送当前分支并等待远端 CI。
2. 在隔离 staging 配置独立 secrets/database，完成 migration、恢复和微信验收。
3. 取得生产备份并证明可恢复。
4. 在 Render 人工选择已验证提交部署；不要开启 auto deploy。
5. 验证 health/ready/login/bootstrap/order/admin/game，再发布微信候选。

## 9. 回滚

1. Render 人工选择上一个已知良好提交。
2. 小程序回退到上一体验版/线上版本。
3. 本轮无数据库 revision，无需因 activity/storage 改动执行 downgrade。
4. 如同时回滚既有 `20260817_14`，必须按其 migration 和备份恢复流程单独处理。
5. 不要以恢复弱秘密、无 owner reconnect token 或自动部署作为回滚手段。

## 10. 未解决问题与风险

- production 当前公开 API 版本仍未由本轮外部核验为 V3；禁止把本地候选描述为线上完成。
- PostgreSQL staging、Neon restore、S3、真实微信登录和两台真机仍待验收。
- outbox/effect ledger 尚未实现，主事务后副作用仍不是严格不丢不重。
- lease epoch fencing 尚未进入持久状态写，跨实例接管仍有旧 owner 写风险。
- `/api/ready` 的认证配置证明、日志 path/key 脱敏、参考数据版本标记和 PostgreSQL CI 仍是 P1。
- 微信能力关闭时首页的持久冷却、查询聚合、图片处理隔离和辅助功能属于后续 P2。
- npm 传递依赖有 deprecated warning；需在单独工具链升级轮次处理，不能无验证地升级 Taro。

## 11. Git 提交摘要

```text
3265f9a audit: complete current project baseline
491f4e9 feat: harden LoveOS V3 backend runtime
c8040ff perf: harden mini-program launch and session state
c9b9185 ops: add free manual release safeguards
docs: add compatibility, verification and release handoff（本文件所在提交）
```
