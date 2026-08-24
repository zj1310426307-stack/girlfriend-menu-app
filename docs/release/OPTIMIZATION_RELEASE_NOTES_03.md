# Continuous Optimization 03 发布说明

- 候选日期：2026-08-24
- 候选分支：`feature/continuous-optimization-03`
- 状态：本地候选完成；远端 PostgreSQL CI、staging 和微信真机待验收

## 本轮亮点

### 迁移风险更早暴露

现有 GitHub Actions backend job 增加 PostgreSQL 18 临时容器，完整覆盖 head 升级、最后一版降级/再升级和 V2 基线升级，同时保留 SQLite。本轮不购买 Neon 分支或其他数据库服务，也不把临时 CI 凭据用于任何外部环境。

### staging 不再靠人工记忆辨别目标

新增只读 readiness 门，只接受独立公共 HTTPS Origin，并拒绝生产复用、重定向、凭据/path/query、直连 IP和本机/内部域名。脚本只读取 health/ready，限制超时和响应大小，日志只输出目标短摘要和组件状态。

微信采用两阶段门：基础设施部署时允许 optional-disabled；真实秘密配置完成后，`--require-wechat` 必须通过才进入小程序构建和真机验收。

## 兼容性

- 业务 HTTP、WebSocket、DTO、token、OpenAPI 和数据库 revision 不变。
- 小程序源码、页面、本地 storage、主包和总包不变。
- 新脚本不进入 FastAPI 或小程序运行时；只由发布人员显式执行。
- CI 只增加临时测试数据库覆盖，不改变 production/staging 连接策略。

## 验证摘要

- 定向：20 passed。
- 后端：272 passed，11 条既有 warning；Ruff、compileall、5 条 Import Linter 合同通过。
- 合同：OpenAPI/schema current；CI YAML 可解析。
- 小程序：完整 CI 与生产构建通过；主包 469,038 B，总产物 888,826 B。
- SQLite：empty/down/up/from-V2 migration matrix 通过。
- 运行：真实 `serve.py` health/ready/dynamic-route smoke 通过，动态房间 sentinel 未进入日志。
- 发布门：免费配置和候选密钥扫描通过。

## 运维动作

1. 推送候选并确认远端 backend job 的 PostgreSQL 与 SQLite 步骤全部通过。
2. 登录 Render，基于 `render.staging.yaml` 创建独立免费 staging 和空数据库，不复制生产数据。
3. 配置独立认证/存储，运行基础 `check_staging_readiness.py`。
4. 配置真实微信秘密并启用登录，运行 `--require-wechat`。
5. 写入 staging Origin，构建微信包并完成开发者工具、体验版与真机验收。
6. 未经单独授权不提交审核、不发布生产。

## 尚未发布与已知限制

本说明不代表 PostgreSQL job、Render staging、微信体验版或真机已通过。当前 Render 未登录，微信开发者工具用户配置未初始化，分支未 push；没有创建云资源或修改生产状态。跨实例订单/评价附属动作严格不丢不重仍需要后续 outbox/effect ledger，房间旧 owner 写入阻断仍需要 lease fencing。
