# LoveOS V3 新窗口交接与继续优化指南

更新时间：2026-08-18（Asia/Shanghai）

仓库：`D:\my-project\girlfriend-menu-app`

远端：<https://github.com/zj1310426307-stack/girlfriend-menu-app>

## 1. 新窗口必须先做的事

1. 完整阅读本文件。
2. 执行只读核对：

   ```powershell
   git status --short --branch
   git log -5 --oneline --decorate
   git diff --stat
   ```

3. 不要清理、回退、覆盖或机械格式化当前工作区；这里有一整组尚未提交的 LoveOS V3 微信生产化改动。
4. 继续优化前，先阅读：
   - `docs/release-v3/README.md`
   - `docs/release-v3/architecture.md`
   - `docs/release-v3/deployment.md`
   - `docs/release-v3/test-report.md`
   - `docs/release-v3/wechat-release-checklist.md`
5. 明确区分以下外部状态：GitHub 发布、后端部署、微信开发版本上传、设置体验版、提交审核、正式发布。它们不是同一件事。

## 2. 当前最重要结论

### 2.1 本地代码

- 当前分支：`feature/wechat-production-v3`。
- 当前 `HEAD`：`aedae15594577d5ef883fdd51760749607e9d4c5`（`LoveOS V3 Game Center Refactor`）。
- `main` / `origin/main`：`641c0d612d2c5b77e731e43271e0b6462fdb52b9`。
- 当前功能分支包含 `main`，并比 `origin/main` 多两个既有提交：
  - `1a17f45 LoveOS V3.0 production refactor`
  - `aedae15 LoveOS V3 Game Center Refactor`
- 在上述提交之上还有大量未提交的微信生产化改动。
- 创建本文件前：33 个已跟踪文件被修改，19 个未跟踪文件，共 52 个修改/新增文件。
- 用户只授权过上传交接文档；除该文档专用远端分支外，不要 commit、push、merge 其他改动，除非用户在新窗口再次明确授权。

### 2.2 GitHub 与部署

- 本轮 `feature/wechat-production-v3` 工作区改动尚未 commit 或 push。
- 交接文档的首个快照已单独上传到远端分支 `agent/thread-handoff-2026-08-18`；该分支相对 `main` 只领先 1 个提交，只新增 `docs/THREAD_HANDOFF_2026-08-18.md`（396 行）。
- 远端文档地址：<https://github.com/zj1310426307-stack/girlfriend-menu-app/blob/agent/thread-handoff-2026-08-18/docs/THREAD_HANDOFF_2026-08-18.md>。
- 尚未为该文档创建 PR，尚未合并到 `main`。本地当前文件包含上传后的最新状态说明，因此应以本地副本为交接权威来源。
- GitHub `main` 尚不包含本轮微信登录、管理账号加固、`/api/bootstrap`、迁移 `20260817_14` 等未提交改动。
- 当前工作区对应的后端没有被证明已部署到 Render staging 或 production。
- 因此，不能把本地测试通过解释为线上后端已经支持当前小程序。
- 以前的 Phase 3.0 / Phase 3.1 GitHub、Render、Neon 记录是历史基线，不代表本轮 V3 工作区已经发布。

### 2.3 微信小程序

- AppID：`wx08cb090781c3e679`。
- 项目：`girlfriend-menu-miniprogram`。
- 当前版本：`3.0.0`。
- 微信开发者工具 CLI 登录状态在上传时为已登录。
- 已成功执行开发版本上传，版本说明为：`LoveOS V3 微信身份、首页与后台安全生产化`。
- 上传结果：成功。
- 包体：总包约 837.3 KB（857,369 bytes），主包约 464.3 KB（475,447 bytes）。
- **尚无权威页面状态或成功提示证明 `3.0.0` 已设为体验版。应按“开发版本已上传、体验版未完成”处理。**
- 没有提交审核，没有正式发布。
- 微信公众平台的网页登录状态可能在新窗口失效，需要重新核对，不能复用旧的临时 `token` URL。

## 3. 本轮已经实现的生产化能力

### 3.1 微信标准身份链路

实现目标：

```text
wx.login
  -> POST /api/customers/wechat-session
  -> 后端固定 HTTPS code2Session
  -> wx_users(app_id, openid, unionid?)
  -> customers
  -> customer_sessions
```

关键行为：

- AppSecret 只存在后端配置中，不进入小程序、Git、OpenAPI 或日志。
- `session_key` 在微信适配器边界被丢弃，不写数据库。
- 新用户仍需 `CUSTOMER_INVITE_CODE`。
- 存量设备可把微信身份绑定到原 `Customer`，不拆分订单、积分、情侣数据或游戏历史。
- 换机可通过同一微信身份恢复同一 `customer_id`。
- 多设备继续使用现有 `customer_sessions`；没有重复建设第二套登录会话表。
- 微信身份冲突返回 409，不静默合并用户。
- 微信网络请求有固定目标、超时、响应校验和错误映射；测试完全 mock，不向微信发送真实测试请求。

关键文件：

- `backend/integrations/wechat.py`
- `backend/services/wechat_auth_service.py`
- `backend/api/routes/auth.py`
- `backend/core/settings.py`
- `miniprogram/src/api/index.js`
- `miniprogram/src/utils/customer.js`
- `backend/tests/test_wechat_integration.py`
- `backend/tests/test_wechat_login.py`

### 3.2 数据库迁移

Alembic 新 head：`20260817_14`。

新增表：

- `wx_users`：微信身份与稳定 `customers.id` 的唯一绑定。
- `admin_accounts`：数据库管理账号，只保存 scrypt verifier。
- `admin_auth_events`：最小化登录结果审计，不保存密码、邀请码、token、IP 或请求体。

明确没有新增：

- 第二套 customer session 表。
- 缺少产品状态机定义的 `couple_bindings` 表。
- 对现有订单、积分、游戏历史的破坏性重写。

关键文件：

- `backend/alembic/versions/20260817_14_wechat_identity.py`
- `backend/models.py`
- `database/v3-schema.sql`
- `backend/tests/test_v3_database_schema.py`

### 3.3 后台认证加固

- 管理密码支持服务端 scrypt 散列。
- 新增数据库管理账号和最小化认证审计。
- 保留旧请求/响应字段兼容。
- 支持从旧配置凭据受控迁移到数据库散列，并支持配置驱动轮换。
- 新增 `scripts/hash_admin_password.py`，用于本地生成 `ADMIN_PASSWORD_HASH`；脚本不回显密码。
- 不要在交接文档、终端输出、聊天或 Git 中记录真实后台密码、管理邀请码、AppSecret 或数据库 URL。

关键文件：

- `backend/services/admin_auth_service.py`
- `backend/auth.py`
- `backend/tests/test_admin_auth_hardening.py`
- `scripts/hash_admin_password.py`

### 3.4 首页聚合与兼容降级

- 新增 `GET /api/bootstrap`，一次返回菜单/推荐、恋爱值、今日任务和最近订单。
- 原有五个首页读取端点均保留。
- 小程序优先请求 bootstrap；不可用时自动降级到旧五请求。
- 菜单本地缓存、WebP 多尺寸、分包和现有 API 请求层继续复用。
- 首页 UI 收敛到首屏核心信息，未改变五个一级 tabBar 入口。

关键文件：

- `backend/api/routes/bootstrap.py`
- `backend/services/bootstrap_service.py`
- `backend/repositories/orders.py`
- `miniprogram/src/api/modules/catalog.js`
- `miniprogram/src/pages/index/index.jsx`
- `miniprogram/src/pages/index/index.css`

### 3.5 配置、就绪探针和发布门禁

- 新增/同步微信登录开关、AppID、AppSecret 和管理密码散列配置。
- `/api/ready` 能区分微信登录关闭、配置完整和 release-blocked。
- `render.yaml`、`.env.example`、发布检查、OpenAPI 和 PostgreSQL schema 快照已同步。
- HTTP `/api/*` operation 当前本地基线为 90。
- WebSocket routes 仍为 3，游戏规则和 WebSocket 协议未因本轮生产化而改变。

## 4. 成熟方案复用原则

本轮延续“成熟方案优先、避免重复造轮子”：

| 能力 | 当前选择 |
| --- | --- |
| API、校验、OpenAPI | FastAPI + Pydantic |
| ORM、事务、迁移 | SQLAlchemy + Alembic |
| 小程序 | Taro + React |
| 缓存/协调 | 现有 Redis adapter，可选降级 |
| 可观测性 | 现有 logging + OpenTelemetry |
| 管理密码散列 | Python/OpenSSL scrypt |
| 微信 code2Session | 标准库固定 HTTPS adapter，5 秒超时 |

没有为单一功能增加新的生产依赖、另一套 session、另一套请求层、另一套 telemetry 或 Nginx。后续优化也应先检索并评估成熟开源方案，再决定是否实现自定义代码；不能为了“使用工具”而扩大依赖或改变稳定协议。

## 5. 已完成验证证据

以下结果属于当前未提交工作区的本地发布候选；任何继续修改都会使相关结论需要按范围重跑。

### 5.1 后端与契约

| 门禁 | 已记录结果 |
| --- | --- |
| Ruff | PASS |
| pytest | PASS，205 passed；11 条既有 SQLite datetime 弃用警告 |
| compileall | PASS |
| Import Linter | PASS，124 files / 381 dependencies / 5 contracts |
| OpenAPI 快照 | PASS |
| PostgreSQL schema 快照 | PASS |
| 密钥扫描 | PASS，461 release-candidate files |
| 发布配置静态检查 | PASS |
| Alembic | PASS，隔离库 upgrade/downgrade/upgrade；head `20260817_14` |

### 5.2 小程序

| 门禁 | 已记录结果 |
| --- | --- |
| `npm run build:weapp` | PASS |
| `npm run test:ci` | PASS；上传前再次执行成功 |
| `npm run test:games` | PASS |
| `npm run test:landlord` | PASS |

### 5.3 本地性能证据

| 场景 | p95 |
| --- | ---: |
| `/api/bootstrap` 五项聚合 | 75.184 ms |
| 旧五请求首屏 | 221.876 ms |
| 五子棋策略 AI | 1.500 ms |
| 房间创建 | 0.025 ms |
| 重连快照恢复 | 0.080 ms |
| 回放序列化 | 0.067 ms |

这些是 Windows 本地隔离 SQLite/Taro 构建结果，不是 Render hosted、真实网络或真机性能结论。

### 5.4 当前工作区检查

- 创建本文件前 `git diff --check` 通过。
- Git 只提示 Windows 工作区中 LF 将来可能被转换为 CRLF；没有报告 whitespace error。

## 6. 已知未完成项和风险

### P0：保护当前未提交工作区

- 不要使用 `git reset --hard`、`git checkout --`、`git clean` 或批量覆盖。
- 先审查 `git diff`，再决定是否继续改代码、拆提交或发布。
- `docs/release-v3/README.md`、`final-report.md` 和 `wechat-release-checklist.md` 仍写着“未上传微信代码”，这一外部状态已经过时；只有在重新核实体验版状态后再统一更新文档。

### P0：前后端版本目前没有线上一致性证据

- 小程序开发版本 `3.0.0` 已上传，但本轮对应后端尚未 commit/push/deploy。
- 设置体验版或真机验收前，应确认小程序所指向的 HTTPS API 环境已经支持：
  - `POST /api/customers/wechat-session`
  - `GET /api/bootstrap`
  - Alembic head `20260817_14`
  - 正确的微信服务端配置与 `/api/ready` 状态
- 如果后端尚未就绪，体验版可能无法完成新微信登录或首页聚合。不要把上传成功等同于端到端可用。

### P0：微信体验版尚未完成闭环

若用户在新窗口仍要求继续发布：

1. 重新确认微信公众平台登录状态。
2. 打开版本管理页面，定位开发版本 `3.0.0`。
3. 只执行“选为体验版/设为体验版”。
4. 以“体验版显示 3.0.0”或明确“设置成功”提示作为完成证据。
5. 不点击“提交审核”，不正式发布。

旧网页登录 URL 中的临时 `token` 不应写入文档或复用。若自动化页面控制不稳定，应停在已上传状态并如实报告，不能猜测成功。

### P1：GitHub 与部署顺序

推荐顺序：

1. 审查当前完整 diff 和敏感信息边界。
2. 重跑完整本地门禁。
3. 经用户授权后再 commit/push/PR 或合并。
4. 部署隔离 staging，配置真实微信后端凭据，运行迁移。
5. 检查 `/api/ready`、新用户、存量绑定、换机恢复、订单和 WebSocket。
6. 完成体验版真机验收。
7. 另行授权后才提交审核或正式发布。

### P1：外部验收仍缺

- Render hosted 冷/热性能证据。
- 真实微信 code2Session staging 流程。
- 新用户邀请码流程、存量用户原地绑定、换机恢复。
- request/socket/upload/download 合法域名与隐私指引复核。
- 真实设备上的首页、订单、图片、五个一级入口、游戏和 WebSocket 冒烟。

## 7. 当前主要修改/新增文件

### 后端

- `backend/.env.example`
- `backend/core/settings.py`
- `backend/api/routes/auth.py`
- `backend/api/routes/bootstrap.py`
- `backend/api/routes/system.py`
- `backend/auth.py`
- `backend/customer_service.py`
- `backend/models.py`
- `backend/schemas.py`
- `backend/repositories/orders.py`
- `backend/services/bootstrap_service.py`
- `backend/services/order_service.py`
- `backend/services/admin_auth_service.py`
- `backend/services/wechat_auth_service.py`
- `backend/integrations/wechat.py`
- `backend/alembic/versions/20260817_14_wechat_identity.py`
- 相关 `backend/tests/` 测试文件

### 小程序

- `miniprogram/src/api/index.js`
- `miniprogram/src/api/modules/catalog.js`
- `miniprogram/src/utils/customer.js`
- `miniprogram/src/pages/index/index.jsx`
- `miniprogram/src/pages/index/index.css`
- `miniprogram/scripts/customer-session-contract-test.cjs`
- `miniprogram/scripts/v3-architecture-test.cjs`

### 发布、快照与文档

- `render.yaml`
- `database/v3-schema.sql`
- `docs/v3-migration/openapi-v3.json`
- `docs/release-v3/`
- `scripts/check_release_config.py`
- `scripts/export_openapi.py`
- `scripts/export_v3_schema.py`
- `scripts/benchmark_v3.py`
- `scripts/hash_admin_password.py`

完整清单以新窗口实时 `git status --short` 为准。

## 8. 完整回归命令

从仓库根目录执行；后端测试使用项目既有隔离机制，不要指向开发或生产数据库。

```powershell
Set-Location D:\my-project\girlfriend-menu-app\backend
python -m ruff check . ../scripts
python -m pytest -q
python -m compileall -q .
python -m alembic -c alembic.ini upgrade head

Set-Location D:\my-project\girlfriend-menu-app\miniprogram
npm run build:weapp
npm run test:ci
npm run test:games
npm run test:landlord

Set-Location D:\my-project\girlfriend-menu-app
git diff --check
```

还应按现有发布文档执行 Import Linter、OpenAPI/schema 快照、密钥扫描和发布配置检查。不要把旧数字沿用为新改动的测试结果。

## 9. 安全边界

- 不提交或展示 `.env`、AppSecret、管理密码、邀请码、数据库 URL、客户 token、openid、unionid、session_key、真实房间码或生产数据。
- 不读取或复制生产数据库行来做 staging 测试。
- 不上传 `node_modules`、`dist`、本地数据库、备份、`.test-tmp`、二维码、截图或微信私有配置。
- `miniprogram/project.private.config.json` 必须继续保持忽略。
- 不为性能优化擅自增加多 worker；当前 WebSocket 和后台任务所有权需要先完成 Redis/多实例复审。
- 不改变游戏规则、WebSocket 协议、旧 Customer/Session 语义或既有 API，除非有单独方案、兼容层和完整回归证据。

## 10. 新窗口建议优先级

1. 保护并审查未提交工作区，确认没有用户在交接后新增改动。
2. 复核当前 V3 代码与 `docs/release-v3/` 的一致性，修正文档中的微信上传状态漂移。
3. 优先解决前后端线上版本不一致，而不是直接做新的性能改造。
4. 在隔离 staging 收集微信登录和 hosted 延迟证据；没有证据前不宣称生产就绪。
5. 体验版完成真机验证后，再决定是否继续产品/UI/性能优化。
6. 所有优化继续遵守：优先寻找成熟开源方案、复用现有边界、避免重复造轮子、先测量后优化。

## 11. 可直接复制到新窗口的启动指令

```text
请先完整读取：
D:\my-project\girlfriend-menu-app\docs\THREAD_HANDOFF_2026-08-18.md

然后在 D:\my-project\girlfriend-menu-app 执行只读检查：
git status --short --branch
git log -5 --oneline --decorate
git diff --stat

当前分支应为 feature/wechat-production-v3，HEAD 应为 aedae15；其上有一整组尚未提交的 LoveOS V3 微信生产化改动。不要 reset、clean、checkout 覆盖或重复实现。

重要外部状态：微信小程序 3.0.0 已成功上传为开发版本，但没有证据证明已设为体验版；本轮对应后端尚未 commit/push/deploy。先确保前后端 staging 一致并复核 /api/ready，再完成体验版设置和真机验收。不要提交审核或正式发布，除非我另行授权。

继续优化时遵循：除非没有成熟方案，否则优先评估并复用开源工具，减少从 0 开发和重复造轮子；不破坏旧 API、Customer Session、WebSocket、游戏规则、数据库历史数据与安全边界。任何改动后按范围重跑 Ruff、pytest、compileall、Alembic、build:weapp、test:ci、test:games、test:landlord、发布门禁和 git diff --check。
```

## 12. 参考资料

- `docs/release-v3/README.md`：当前生产化发布包索引。
- `docs/release-v3/architecture.md`：微信身份、数据模型、首屏和部署取舍。
- `docs/release-v3/deployment.md`：部署顺序与回滚。
- `docs/release-v3/monitoring.md`：健康、就绪、日志、追踪与告警边界。
- `docs/release-v3/test-report.md`：当前本地 RC 测试证据。
- `docs/release-v3/wechat-release-checklist.md`：微信上线前检查项。
- `docs/optimization/PHASE_3_0_PRECHECK.md`：Phase 3.0 前置审查。
- `docs/optimization/PHASE_3_0_R2A_GUARDRAILS_REVIEW.md`：配置/架构门禁。
- `docs/optimization/PHASE_3_0_R2B1_TRACE_FOUNDATION_REVIEW.md`：Trace 核心基础。
- `docs/optimization/PHASE_3_0_R2B2_INSTRUMENTATION_POC_REVIEW.md`：框架与数据库插桩 PoC。
- `docs/optimization/PHASE_3_0_R2C_TEST_ISOLATION_REVIEW.md`：测试与诊断隔离。
- `docs/optimization/PHASE_3_1_A_HOSTED_TEST_PLAN.md`：hosted 证据采集边界。
- `docs/optimization/PHASE_3_1_A_HOSTED_LATENCY_REPORT.md`：历史 hosted 证据状态；不要误当作本轮 V3 已部署证明。
