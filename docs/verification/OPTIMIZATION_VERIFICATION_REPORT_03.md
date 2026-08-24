# Continuous Optimization 03 验证报告

- 验证日期：2026-08-24
- 分支：`feature/continuous-optimization-03`
- 结论：本地候选通过；远端 PostgreSQL CI、隔离 staging、微信体验版/真机和 production 未执行

## 1. 变更范围

- GitHub Actions backend job 增加 PostgreSQL 18 临时 service 与六个迁移步骤。
- 新增 staging 只读 readiness 工具及 20 项失败关闭/状态合同测试。
- 同步 backlog、当前架构、部署、监控、微信清单和本轮交付材料。
- 无业务 API、OpenAPI、数据库 revision、小程序运行时代码或包体逻辑变化。

## 2. 定向测试

`tests/test_staging_delivery_gates.py`：20 passed，覆盖：

- 空值、HTTP、凭据、path/query/fragment、非 443、localhost、直连 IP、内部域名和生产复用在网络前失败；
- 只请求 health/ready，不触发业务写接口；
- PostgreSQL、持久存储、认证、Redis 和顶层状态判定；
- 微信 optional-disabled 基础模式与 require-wechat 真机模式；
- workflow 同时保留 SQLite 与 PostgreSQL 18、down/up 和 from-V2 合同。

脚本在无 `STAGING_API_ORIGIN` 时实际退出码为 1，且只输出 `STAGING_API_ORIGIN is required`，没有发起网络请求。

## 3. 后端全量与架构门

| 门禁 | 结果 |
| --- | --- |
| pytest | PASS：272 passed，11 warnings |
| Ruff | PASS |
| Import Linter | PASS：129 files、416 dependencies、5 contracts |
| compileall | PASS |
| OpenAPI 快照 | current |
| PostgreSQL schema 快照 | current |
| 本地性能预算 | PASS |

11 条 warning 仍来自 Python 3.12 的 SQLite 默认 datetime adapter 弃用提示；本轮未新增 warning 或测试失败。

本地 benchmark 使用 TestClient + 隔离 SQLite：bootstrap p95 42.910 ms，旧五请求 p95 95.506 ms，房间创建 p95 0.030 ms，重连 p95 0.073 ms，回放 p95 0.069 ms，全部低于现有预算。这些数据不是 hosted 或真机性能。

## 4. 数据库迁移

两个显式临时 SQLite 文件完成并已清理：

1. 空库 upgrade head 到 `20260817_14`。
2. downgrade 到 `20260817_13` 后再次 upgrade head。
3. 独立空库 upgrade 到 `20260808_01`，再到 head。

CI YAML 已通过本地解析，源码合同确认 `postgres:18-alpine` 和六个 PostgreSQL 命令存在。但本机没有 Docker/PostgreSQL，分支未推送，所以没有 PostgreSQL DDL 实际执行证据；该项保持外部验收。

## 5. 小程序与包体

- `npm run test:ci`：PASS。
- `npm run build:weapp`：PASS，Taro 4.2.0。
- 主包：57 files / 469,038 B。
- 总产物：182 files / 888,826 B。

本轮没有修改小程序运行时，产物与第二轮完全相同。未配置独立 Origin 的 staging 构建继续失败关闭；没有用生产 Origin 生成 staging 包。

## 6. 真实本地启动与隐私

使用独立临时 SQLite 和显式合成测试凭据启动 `serve.py`：

- migration/seed 完成，Uvicorn application startup complete；
- `/api/health` 返回 ok，`/api/ready` 返回 ready；
- authentication/storage ready，微信 optional-disabled；
- 动态房间请求返回 404，日志只记录 `/api/games/rooms/{room_code}`，不含 sentinel 原文；
- 进程停止后临时数据库已删除。

## 7. 发布安全门

- `check_release_config.py`：PASS，三套 Blueprint 保持 free + manual deploy。
- `check_secrets.py`：PASS，503 个 release-candidate files。
- `git diff --check`：PASS。
- 无新依赖、无付费资源、无生产部署、无业务数据写入。

## 8. 外部状态核对

- Render：应用内浏览器和 Chrome 均停在登录页；没有凭据和已登录会话，未创建/修改 service、database 或 secret。
- staging：仓库 `.env.staging` 仍故意保持空 Origin；没有独立 staging URL，未运行 hosted 只读门。
- 微信：普通微信客户端存在私人聊天窗口，本轮未触碰；开发者工具 CLI 因用户配置目录缺少 `.cli` 而无法连接，GUI 也没有可定位窗口，因此没有模拟器、预览码、体验版或真机证据。
- GitHub：本轮只创建本地提交，未 push，未触发 PostgreSQL Actions job。

因此当前状态是“免费交付门本地候选完成、外部 staging/真机待接力”，不是已上线或生产就绪。

## 9. 剩余风险

- PostgreSQL JSONB、表锁和 downgrade 行为必须由远端 CI 与隔离 staging 实测确认。
- 免费 Render 冷启动、跨区域 RTT 和微信真实网络启动 P95 仍无新证据。
- 跨实例附属动作严格不丢不重仍需 transactional outbox/effect ledger。
- 房间 lease fencing、全局 scheduler ownership、参考数据版本标记仍在 backlog。
