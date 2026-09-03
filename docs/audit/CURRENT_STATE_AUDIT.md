# LoveOS V3 当前状态审计

- 审计日期：2026-08-24
- 审计对象：`girlfriend-menu-app` 当前工作区
- 当前分支：`feature/wechat-production-v3`
- 当前提交：`aedae15594577d5ef883fdd51760749607e9d4c5`（相对 `main` 超前 2 个提交）
- 审计方式：仓库、配置、迁移、测试、构建和发布材料的只读检查；未访问生产数据，未部署，未产生付费资源

## 1. 审计结论

当前项目已经具备一套可运行的 LoveOS V3 产品候选：业务功能覆盖菜单、下单、情侣互动、通知、积分排行、小游戏、管理端和图片上传；后端有正式 Alembic 迁移、分层约束和较完整的自动化门禁；小程序已经完成分包与本地优先快照，包体健康。

本地证据表明候选版本具备继续产品化的基础，但**当前工作区不是可直接发布的制品**：有 56 个已跟踪文件改动和 30 个未跟踪文件，其中包括生产启动入口、最新迁移、测试和发布配置。任何漏提交都可能让部署入口或数据库结构不完整。因此本轮没有发现明确的运行时 P0 漏洞，但存在一个必须先消除的 P0 级发布阻断。

最值得本轮立即处理的两个产品问题是：

1. 每次已登录 API 请求都会刷新 `last_seen_at` 并提交远程数据库事务，使首页和各 Tab 的读取请求被放大成读写请求。
2. 小程序会话清理没有覆盖购物车、复购草稿和游戏恢复凭证；游戏恢复 token 仅按房间号存储，同设备切换账号时可能恢复前一账号的房间。

生产发布还有两项低成本高收益防线：生产 Blueprint 当前允许自动部署，而启动入口会自动迁移；环境模板和逻辑备份脚本仍含已知弱默认值。本轮可以在不改变公开 API、不新增数据库迁移、不购买服务的前提下完成修复。

## 2. 当前产品功能

### 2.1 客户端

- 邀请码创建、恢复、刷新和撤销客户会话。
- 可选微信身份绑定；微信能力未配置时保留邀请码路径。
- 菜单浏览、分类筛选、收藏、购物车、复购和订单详情。
- 情侣任务、纪念日、记忆、通知和积分排行。
- 游戏大厅及多种本地/在线小游戏，包含 WebSocket 实时状态、重连凭证和持久化对局。
- 首页及主要 Tab 的本地快照、请求所有权和刷新冷却，减少免费实例唤醒时的白屏。

### 2.2 管理端

- 管理员登录、菜品管理、订单管理、状态流转和图片上传。
- 管理员密码散列、签名 token、版本轮换和频率限制基础能力。

### 2.3 后端与数据

- FastAPI HTTP API、3 条 WebSocket 路由和轻量 `/api/health`、依赖检查 `/api/ready`。
- 37 个 SQLAlchemy 表；14 个线性 Alembic revision，当前 head 为 `20260817_14`。
- PostgreSQL 作为托管目标，SQLite 作为本地和现有 CI 测试数据库。
- 数据库或 S3 持久化图片；Redis 为可选缓存/限流适配器。
- 免费实例启动入口 `backend/serve.py`：仅在迁移 head 或参考数据计数不完整时执行迁移/种子，正常唤醒走快速路径。

## 3. 架构与边界

```text
微信小程序（Taro/React）
  -> 集中请求传输层 / 手写 API wrapper
  -> FastAPI 路由
  -> service / rules / repository
  -> PostgreSQL 或本地 SQLite

在线游戏
  -> WebSocket 路由 / 会话服务
  -> 数据库快照、租约、动作回执
  -> 进程内连接中心（单实例实时广播）

图片
  -> 管理端上传路由
  -> Pillow 变体处理
  -> database 或 S3 provider
```

已建立的正向边界：

- `backend/.importlinter` 有 5 条架构契约，限制 API、service、repository、纯规则和 AI 模块的依赖方向。
- API 请求集中在 `miniprogram/src/api/transport.js` 和 `miniprogram/src/api/index.js`。
- 订单、评价、游戏动作已有数据库唯一键或状态检查来保护主要幂等语义。
- 数据库被视为订单、身份和持久化游戏状态的权威源；前端快照仅承担快速展示和降级。

仍需收敛的边界：

- 部分路由仍直接修改 ORM 并提交，部分 repository 自行提交，业务事务组合不统一。
- 订单/评价主事务后的积分、通知、记忆和广播没有 durable outbox/effect ledger。
- 游戏租约虽有 `lease_epoch`，但状态写入未使用 owner/epoch fencing。
- 前端 API wrapper 仍由人工维护，OpenAPI 快照未生成客户端或运行时 schema。

## 4. 技术栈与依赖

| 层 | 当前事实 |
| --- | --- |
| 小程序 | Taro 4.2、React 18.3、JavaScript/JSX、Webpack 5 |
| API | FastAPI 0.115.12、Uvicorn 0.34.2、Pydantic 2.11.4 |
| 数据 | SQLAlchemy 2.0.40、Alembic 1.14.1、psycopg2-binary 2.9.10 |
| 图片/存储 | Pillow 11.3、boto3 1.40、数据库或 S3 provider |
| 可选基础设施 | Redis 5.2、OpenTelemetry API/SDK |
| 托管候选 | Render 免费 Web Service；Neon PostgreSQL；不使用付费保活 |

直接依赖有精确版本，但 Python 传递依赖没有带 hash 的完整锁文件。npm 使用 lockfile 和 `npm ci`，可复现性更好。

## 5. 测试、构建与 CI/CD

### 5.1 已有门禁

- 后端：Alembic upgrade/downgrade/from-V2、Ruff、Import Linter、compileall、schema/OpenAPI 快照、pytest 和性能预算。
- 小程序：`npm ci`、微信生产构建、游戏/会话/架构/核心流程/启动和 Tab 契约测试。
- 发布安全：密钥扫描和 Blueprint/小程序环境静态检查。
- Dependabot 已覆盖 npm、pip 和 GitHub Actions。

### 5.2 最近一次本地基线

以下结果来自本轮开始前同一工作区的已记录验证，尚未代表远端 CI：

- 后端 pytest：228 passed。
- Ruff、Import Linter（128 文件、408 依赖、5 契约）、compileall：通过。
- 小程序 `npm run test:ci` 与 `build:weapp`：通过。
- 微信产物：主包 467,041 B，分包 420,844 B，总计 887,885 B。
- 空 SQLite 首次迁移+种子约 1.388 秒；第二次快速唤醒约 5 ms。
- 本地统一启动入口可启动 Uvicorn，`/api/health` 返回 200。

这些结果将在本轮改动后重新验证并写入独立验证报告。

### 5.3 覆盖缺口

- Alembic CI 只在 SQLite 上运行，未验证 PostgreSQL DDL、锁和约束行为。
- 小程序多数契约测试基于源码正则，缺少真实 storage、账号切换和并发状态机行为测试。
- 微信 DevTools 脚本未全部进入 CI；没有自动化真机、可访问性和图片尺寸预算测试。
- 发布检查主要依赖文本匹配；密钥扫描排除了 `.env.example` 和小程序 env，覆盖范围有限。

## 6. 性能审计

### P1：认证热路径写放大

- `backend/api/dependencies.py` 的每个 bearer 请求都会调用 `customer_service.authenticate()`。
- `backend/customer_service.py` 在正常 session 命中后每次更新 session/customer 的 `last_seen_at` 并 `commit()`。
- 随后 `user_service.ensure_user()` 还会执行一次用户查询。

影响：免费远程数据库的写往返、WAL、连接占用和失败面进入了所有读取请求，首页 bootstrap 和快速切换 Tab 都受影响。

建议：只对 `last_seen_at` 做服务端时间窗口节流，并用条件更新防止并发请求重复触碰；撤销、过期和停用判断保持逐请求执行。

### P1：免费环境重复探测不可用微信能力

生产免费 Blueprint 当前关闭微信登录，但首页已有会话仍会执行 `Taro.login` 和 `/customers/wechat-session`，503 仅被吞掉，没有持久能力冷却。这会与 bootstrap 并发唤醒后端。该项列入下一小轮，避免和本轮身份状态修复混杂。

### P2：查询与图片处理

- 订单模型 `status_events` 使用 `selectin`，公开订单响应却不消费该历史，可能产生额外查询。
- 首页积分摘要把全部历史积分加载到 Python 再聚合。
- 常用订单列表缺少与过滤/排序一致的组合索引。
- 图片解码、变体处理和 provider 写入在 async 上传路由中同步执行；有 5 MB 文件上限，但缺显式像素/边长上限。

## 7. 安全与隐私审计

### P1：同设备客户状态越界

- `cart.js` 使用全局购物车和复购草稿键。
- `gameRecovery.js` 的重连 token 仅按 `roomCode` 保存。
- `clearCustomerSession()` 没有清理上述数据。
- `/api/games/reconnect` 按 token 恢复原用户和房间，不需要当前 bearer。
- `gameSocket.js` 还会长期保存全仓没有读取方的 `room_session_token`。

影响：同设备从客户 A 切到客户 B 后，B 可能看到 A 的菜品、备注、复购来源，或使用 A 遗留 token 恢复 A 的游戏房间。

建议：新重连键加入 customer owner；旧无 owner token 不迁移；清会话和 owner 切换时清理购物车、草稿、重连和 room-session secret；停止保存未使用 secret。

### P1：发布凭据与日志

- `.env.example` 仍包含 `admin123`、`love2026` 和已知 placeholder secret。
- 生产 API 逻辑备份脚本默认使用公开生产域名和 `love2026`。
- HTTP 中间件记录真实 path，游戏房间码会进入 path；部分缓存/维护日志记录原始 key 或房间码。

本轮先去掉弱默认并加强静态发布门；日志统一脱敏列入后续专门轮次。

### 其他风险

- 管理员被停用后，已签 token 在过期或 `ADMIN_TOKEN_VERSION` 轮换前仍可使用。
- legacy 身份恢复依赖共享邀请码和可知 legacy ID，是过渡兼容面。
- `/api/ready` 尚未证明客户/管理员关键认证配置完整。

## 8. 数据库与迁移审计

- 当前 migration 链线性，无已知分叉；生产候选需从既有版本升级到 `20260817_14`。
- `serve.py` 在 managed 环境发现 revision 漂移时自动执行 Alembic；当前生产 `autoDeploy: true` 会把代码发布和数据库迁移绑定在一起。
- PostgreSQL 临时恢复演练仍未取得证据；正式备份仍是人工流程。
- 免费启动用表数量下限判断参考数据是否完整，无法识别“数量不变但内容变更”；后续应引入持久化参考数据版本标记。

本轮代码不改变表、索引或数据格式，因此不新增 Alembic revision。

## 9. 可维护性与技术债

- 超大文件包括 `game_runtime/manager.py`、`models.py`、`schemas.py`、`order_service.py` 和前端 `api/index.js`。
- Python Ruff 当前只选择 `F` 规则，风格与复杂度覆盖较窄。
- README、Procfile、测试数量和新 `serve.py` 启动链存在文档漂移。
- 仓库没有 `.gitattributes`，Windows 环境出现 LF/CRLF 噪声风险。
- `test:v28` 仍指向 V2.7 脚本。
- 当前工作区混合了多轮未提交变更，妨碍逻辑提交、代码审查和可复现发布。

## 10. 外部验收状态

以下事项没有在本轮本地审计中被证明，不能表述为已通过：

- 隔离 staging 部署、Neon PostgreSQL 真迁移与恢复。
- 微信体验版、真实登录态和两台真机核心流程。
- 免费托管实例真实冷启动/唤醒延迟。
- S3 provider 真实凭据与持久化。
- 两实例 WebSocket、租约接管、严格不丢不重副作用。

## 11. 总体建议顺序

1. 冻结安全分支和候选文件清单，禁止从当前脏工作区直接部署。
2. 本轮完成认证 last-seen 节流、客户本地状态隔离、生产手动发布门和弱默认清理。
3. 全量回归并生成兼容/迁移、验证和发布说明。
4. 在免费隔离 staging 完成 PostgreSQL、微信 DevTools/真机和 hosted wake 验收。
5. 下一架构轮次设计 outbox/effect ledger 与 lease fencing；它们是跨实例严格不丢不重的必要条件。

