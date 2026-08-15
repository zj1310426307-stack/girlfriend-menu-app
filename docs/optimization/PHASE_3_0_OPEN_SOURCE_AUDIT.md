# Phase 3.0 Round 1 — Open Source & Architecture Audit

> 审计日期：2026-08-14（Asia/Shanghai）
>
> 审计基线：`845fa51a649a3a2e4bec1200099618128a5b0b3d`
>
> 范围：只读架构与开源方案审计；本文件是本轮唯一新增交付物
>
> 结论：**ROUND 1 AUDIT COMPLETE — WAITING FOR HUMAN REVIEW**

本报告使用仓库当前代码、最近 Git 历史、已恢复的 B1 基线和开源项目官方资料作出
决策。开源项目的活跃度与版本信息以审计日可见信息为准，不构成自动升级授权。

## 1. Executive Summary

当前系统是一个已开始模块化、但仍保留兼容门面的 FastAPI + Taro 模块化单体。
它不是需要推倒重建的遗留系统。数据库持久化、可选 Redis 热缓存、游戏房间 CAS
租约、断线恢复、隐私过滤、结算恢复、图片存储抽象和完整发布门禁已经形成有效基础。

本轮发现的主要工程问题是：

1. 约 29 处生产/运维环境变量读取分散，类型转换、默认值和“何时失败”由各模块各自负责；
2. 路由 → 服务 → 仓储主路径已存在，但 `crud.py` 兼容门面、共享 `models.py` /
   `schemas.py`、服务层直接抛 `HTTPException` 使边界仍可能回退；
3. 当前只有 HTTP 总耗时日志，无法把已记录的 First State `4.9～9.8s` 和
   Settlement Visibility `约 34.5s` 分解到 DB、快照、租约、结算和通知阶段；
4. 大模块风险集中在前端 API 门面、共享模型/Schema、游戏路由和刚完成稳定化的实时
   manager；“文件大”本身不构成立刻拆分理由。

最终只推荐 3 个 `ADOPT_NOW`：

| 优先级 | 方案 | 决策理由 |
|---|---|---|
| P0 | `pydantic-settings` | 与现有 Pydantic 2/Python 3.12 同生态；可保持环境变量名、默认值与现有延迟失败语义，集中校验并减少重复 `getenv`。 |
| P0 | `import-linter` | 用成熟、低运行风险的开发工具冻结当前已经形成的依赖边界，避免自研 AST 检查器。 |
| P0 | OpenTelemetry Python（可选启用） | 先定位真实耗时，不凭感觉优化；无 exporter/无配置时必须保持 no-op，不改变 API、WebSocket 或业务语义。 |

其余关键结论：

- `auth.py`、Rate Limit、Cache、Storage、WebSocket 和 Game Runtime 均 `KEEP_CURRENT`；
- 普通周期任务、OpenAPI 客户端生成、生产备份/PITR `ADOPT_LATER`；Dependabot 已存在，
  CI / Dependency Management `KEEP_CURRENT`，后续只调优配置；
- 不引入 Celery、RabbitMQ、Kafka，不迁移 Colyseus/Nakama/boardgame.io/Socket.IO，
  不全量替换 TDesign/Vant，不整体搬目录；
- `game_runtime/manager.py` 明确为 **DEFER STRUCTURAL REFACTOR**；
- Round 1 未新增生产依赖、开发依赖、Migration，也未修改 API、WebSocket、业务或 UI。

## 2. Current Architecture

### 2.1 已验证基线

本轮沿用的不是旧估算，而是 B1 已完整恢复并通过 Gate 的真实基线：

| 项目 | 结果 |
|---|---|
| Git SHA | `845fa51a649a3a2e4bec1200099618128a5b0b3d` |
| Python | `3.12.13` |
| pytest | `110 passed`，11 warnings |
| Alembic head | `20260812_12` |
| HTTP operations | `88` |
| WebSocket paths | `3` |
| Taro | `4.2.0` |
| 小程序 dist | 137 files，803,033 bytes |

Round 1 实际变更预算：

| 项目 | 数量 |
|---|---:|
| 新增生产依赖 | 0 |
| 新增开发依赖 | 0 |
| 数据库 Migration | 0 |
| HTTP API 修改 | 0 |
| WebSocket 修改 | 0 |
| 业务功能修改 | 0 |
| UI 行为修改 | 0 |

审计开始时工作区包含受保护的 B0 测试修复，以及未跟踪的 Precheck/B0/B1/交接文档。
本轮没有 reset、checkout、clean 或覆盖这些文件。

### 2.2 运行时结构

```text
Taro / 微信小程序
  ├─ src/api/index.js        HTTP、Bearer、重试、错误映射、菜品缓存、上传
  └─ src/api/gameSocket.js   原生 WebSocket、心跳、重连、待发队列
             │
             ▼
FastAPI api/routes
             │
             ▼
services + 部分旧顶层 service / crud compatibility facade
             │
             ▼
repositories / SQLAlchemy / PostgreSQL(or SQLite local)

实时游戏旁路：
WebSocket route → socket session service → lease/state store → GameRoomManager
  ├─ PostgreSQL durable state（事实来源）
  ├─ Redis optional hot cache
  └─ process memory（短期热状态/降级）
```

部署清单当前是 Render `free` 单 Web Service，启动时先执行 Alembic，再启动 Uvicorn。
Redis 是可选项；图片生产配置当前选择 PostgreSQL provider。仓库没有多实例部署配置，因此
现阶段不能仅凭“未来可能水平扩展”改写现有运行时。

### 2.3 已有优势

- API 路由已经拆入 `api/routes`，业务服务和 6 个仓储模块已经存在；
- 仓储通常拥有事务提交，`crud.py` 大部分函数已变成兼容转发；
- 游戏规则/AI/engine 主体没有依赖 FastAPI、SQLAlchemy 或数据库；
- 实时状态以 PostgreSQL 为 durable truth，Redis 只是可选加速，不是正确性单点；
- CAS lease、重连、首状态、结算幂等/恢复、协议与隐私均有针对性测试；
- Local/S3-compatible/PostgreSQL 三种图片 provider 已共享同一抽象；
- CI 已覆盖迁移升降级、Ruff、compileall、pytest、小程序构建和契约脚本；
- 备份脚本已有哈希、行数 manifest 和隔离恢复校验。

### 2.4 当前结构缺口

- `crud.py` 仍承载游戏统计与过期处理等残余逻辑，同时充当旧调用兼容门面；
- 一部分 `services` 和 `games/core` 直接依赖 `HTTPException`、`Session` 或自行提交事务；
  其中 `games/core/room.py`、`player.py`、`state.py`、`service.py` 实际是应用/持久化层，
  不能把它们误标为纯规则层；
- `models.py` 有 31 个 ORM class，`schemas.py` 有 70 余个 Pydantic class，跨域共享；
- `miniprogram/src/api/index.js` 集中约 70 个 HTTP 导出，变更频繁；
- `main.py` 同时拥有三种不同可靠性要求的周期循环；
- HTTP 429 在依赖函数中返回 JSON `detail`，在 middleware 中返回纯文本，现状需要冻结而非
  在本阶段顺带统一；
- 可观测性只到 request total duration，无法解释实时链路慢在哪里。

### 2.5 指定自研模块审计

| 模块 | LOC | 当前职责与证据 | 核心性 / 结论 |
|---|---:|---|---|
| `backend/auth.py` | 76 | Customer credential 生成/哈希；Admin HMAC token 签发验证；延迟读取 secret/version | 安全敏感、产品身份语义；`KEEP_CURRENT`，配置读取后续集中，token 格式不改 |
| `backend/core/rate_limit.py` | 61 | 进程内 deque 滑窗、Redis 固定窗口、启动 ping 与内存降级 | 基础设施保护；`KEEP_CURRENT`，当前规模无替换收益 |
| `backend/core/cache.py` | 99 | Redis JSON/presence/game hot cache，30 秒重连，故障 best-effort | 非事实来源；`KEEP_CURRENT` |
| `backend/core/game_state_store.py` | 174 | Memory/Redis/DB 三实现，PostgreSQL durable-first，防 stale cache 复活 | 实时正确性核心；`KEEP_CURRENT` |
| `backend/core/game_room_lease.py` | 151 | DB compare-and-set acquire/renew/release，epoch 与到期时间 | 防 split-brain 核心；`KEEP_CURRENT`，heartbeat 不迁普通 scheduler |
| `backend/storage.py` | 171 | Local/S3/DB provider，图片验证/重编码，release readiness | 抽象已足够；`KEEP_CURRENT` |
| `backend/database.py` | 119 | dotenv、URL 归一化、engine/pool、Session、仅开发/测试 compatibility DDL | 关键基础设施；SQLAlchemy/Alembic 已成熟，`KEEP_CURRENT`；配置读取后续集中 |
| `backend/main.py` | 186 | app assembly、中间件、seed/lifespan、anniversary、game cleanup、lease heartbeat | 生命周期边界；lease 保留，普通任务 `ADOPT_LATER`，request tracing `ADOPT_NOW` |
| `backend/game_runtime/manager.py` | 828 | 内存 room、快照队列/恢复、连接、action dispatch、隐私 payload、完成事件 | 实时核心且刚稳定；`KEEP_CURRENT` + `DEFER STRUCTURAL REFACTOR` |
| `backend/services/game_socket_session_service.py` | 245 | room/lease、runtime restore、player auth、membership、join/disconnect/status | WS 应用编排；`KEEP_CURRENT`，是 join/restore/lease spans 的落点 |
| `backend/services/game_persistence_service.py` | 352 | room/player/session 持久化、join、token、finish/list，调用 repository 但仍抛 `HTTPException` | 应用服务；`KEEP_CURRENT`，后续逐片换 domain exception，不大重写 |
| `backend/services/game_settlement_service.py` | 98 | 完成事件落库、积分/replay/notification、异步 retry/ack 恢复 | 结算正确性核心；`KEEP_CURRENT`，优先加阶段观测 |
| `backend/crud.py` | 529 | 新 service 的 compatibility facade，加残余过期/统计逻辑 | 高变更兼容边界；继续 Strangler，P1 收缩，不整体重写 |
| `backend/models.py` | 714 | 31 个跨 customer/order/game/couple/notification/task 的 ORM class | DB 共享契约；以后兼容 re-export 拆分，当前 `KEEP_CURRENT` |
| `backend/schemas.py` | 736 | 70 余个跨域 request/response model | 88 个 HTTP operation 的公共契约；P2 分域但不改 schema |
| `miniprogram/src/api/index.js` | 566 | Taro transport、retry、Bearer/401、错误、cache、upload、约 70 个 endpoint exports | 高频 HTTP compatibility facade；P1 按域拆，生成 client 仅 `ADOPT_LATER` PoC |
| `miniprogram/src/api/gameSocket.js` | 242 | 原生 socket、25s heartbeat、指数抖动重连、20 条队列、session join | WS 契约核心；`KEEP_CURRENT`，不换 Socket.IO |

## 3. OSS Decision Matrix

“减少自研”是对可删除/避免继续增长代码的定性估计，不是要求立即删除。活跃表示审计日有
近期发布/提交或已稳定维护；托管服务的条款与开源代码 License 分开表述。

| # | 类别 | 当前实现 / 是否核心业务 | 成熟候选（License / 活跃度） | Python、Taro、微信兼容性 | 迁移难度 / 可减少自研 / 新复杂度 | 决策 |
|---:|---|---|---|---|---|---|
| 1 | 配置管理 | 约 29 处 `getenv`，`python-dotenv` 仅在 DB 等入口使用；非核心业务 | `pydantic-settings`（MIT；2.14.2 于 2026-06 发布，活跃） | Python 3.12、Pydantic 2 原生适配；不影响小程序 | 中 / 可收敛大部分解析、默认值和校验 / 引入集中初始化与测试隔离要求 | **ADOPT_NOW** |
| 2 | 认证与凭证 | Customer opaque session + 哈希、轮换、撤销、legacy 迁移；Admin HMAC token；安全敏感但产品特有 | PyJWT（MIT；2.13.0，活跃）、Authlib（BSD-3-Clause，活跃）、FastAPI Users（MIT，维护模式）、Supabase Auth（托管条款+开源组件） | Python 可用；但都会改变 token/account 模型，小程序需兼容迁移 | 高 / PyJWT 只替代少量 Admin 签名代码 / token 双读、账户表和供应商依赖 | **KEEP_CURRENT** |
| 3 | Rate Limit | 61 LOC：内存滑窗 + Redis 固定窗；认证、上传、建/入房使用；基础设施保护 | `limits`（MIT；5.8，Production/Stable）、SlowAPI（MIT；维护中） | `limits` 支持 Python 3.12/Redis；SlowAPI 对 WebSocket 无覆盖且有适配约束 | 中 / 约 61 LOC / 策略、key、429 契约和故障降级要重测 | **KEEP_CURRENT** |
| 4 | Cache | `redis-py` + 99 LOC best-effort JSON wrapper，DB/内存降级；非业务核心 | `redis-py`（MIT，已采用、活跃）；dogpile 等不能替代 durable state 语义 | Python 3.12 可用；小程序无直接影响 | 高（若换）/ 很少 / 新 cache abstraction 不增加正确性 | **KEEP_CURRENT** |
| 5 | Storage | 171 LOC Local/S3-compatible/PostgreSQL provider + Pillow 校验；基础设施边界 | boto3（Apache-2.0，已采用）、S3/R2/MinIO/Supabase Storage（provider/服务选择） | S3-compatible 与 Python 兼容；返回 URL/API 对小程序已稳定 | 高（若重构）/ 几乎无 / provider 运维、凭证和迁移 | **KEEP_CURRENT** |
| 6 | Logging | Python `logging` + 隐私安全 request line；非核心业务 | stdlib（PSF License，稳定）、structlog（Apache-2.0，活跃） | 完全兼容 | 低到中 / 少量格式代码 / 日志 schema 与采集配置 | **KEEP_CURRENT** |
| 7 | Observability | 仅 request total latency 和异常日志；基础设施能力 | OpenTelemetry Python API/SDK + FastAPI/SQLAlchemy instrumentation（Apache-2.0；1.44/0.65b 系列持续发布） | Python 3.12 支持；服务端透明，不改 Taro/微信协议 | 中 / 避免自研 tracing SDK / span 设计、开销、隐私、可选 exporter | **ADOPT_NOW** |
| 8 | Background Jobs | `main.py` 三个 asyncio 循环；lease 是实时核心，其余为维护任务 | APScheduler（MIT；3.11.2 稳定活跃，4.x 仍需谨慎）、Render Cron（托管服务） | Python/Render 兼容；不影响小程序 | 中 / 删除普通循环 / 多实例、调度归属、失败重试与成本 | **ADOPT_LATER** |
| 9 | Retry | 小程序仅 GET 做 2 次线性退避；结算有定点重试；语义敏感 | Tenacity（Apache-2.0，活跃）、p-retry（MIT，活跃） | Tenacity 适合 Python；p-retry 的标准 JS 运行环境不等于微信验证 | 中 / 少量 / 幂等策略可能被通用库掩盖 | **KEEP_CURRENT** |
| 10 | HTTP Client | 后端生产无通用外呼；测试用 httpx；前端统一 `Taro.request`/`uploadFile` | httpx（BSD-3-Clause，活跃）、Taro（MIT，已采用） | 当前 Taro 路径是微信兼容基线；原生 fetch 生成器不当然兼容 | 高（若换）/ 只减少 wrapper 一部分 / 上传、Bearer、401、错误语义重做 | **KEEP_CURRENT** |
| 11 | OpenAPI Client Generation | 566 LOC 手写 API 门面；非核心业务但契约风险高 | OpenAPI Generator（Apache-2.0，活跃）、Orval（MIT，活跃）、openapi-typescript（MIT，活跃） | Orval custom mutator 可接 `Taro.request`；标准 fetch 生成物需验证；当前前端为 JS | 中 / 中长期可减少 endpoint wrapper / TS 工具链、生成噪音、bundle 与 WebSocket 仍手写 | **ADOPT_LATER** |
| 12 | Database | SQLAlchemy 2 + Alembic + PostgreSQL/SQLite；关键基础设施 | SQLAlchemy/Alembic（MIT，已采用且活跃） | Python 3.12 已由基线验证 | 极高（若换）/ 无 / 数据与迁移风险 | **KEEP_CURRENT** |
| 13 | Repository Layer | 6 个函数式 repository + `crud.py` 兼容门面；应用架构 | SQLAlchemy repository/unit-of-work patterns；无必要引入通用 repository 框架 | 当前栈原生 | 中 / 只能减少少量样板 / 会增加抽象泄漏和泛型层，且不能表达业务事务 | **KEEP_CURRENT** |
| 14 | Architecture Dependency Enforcement | 靠评审和测试，没有机器化边界；工程治理 | `import-linter`（BSD-2-Clause；2.13 于 2026-07 发布，支持 Python 3.12/Windows） | 只在 Python CI 运行；不影响小程序 | 低 / 避免自研 AST 工具 / 配置与合理例外维护 | **ADOPT_NOW** |
| 15 | Frontend Component Library | 领域组件丰富；基础状态用 `AsyncState`，Toast/Modal/Picker 用 Taro 原生；视觉是产品资产 | TDesign Miniprogram（MIT；1.15.0/143 releases，活跃）、Vant Weapp（MIT，成熟） | 原生微信兼容好，但 Taro React 接入和样式覆盖需逐组件验证 | 高（全量）/ 复杂控件可少写 / 主题冲突、bundle、双组件体系 | **KEEP_CURRENT** |
| 16 | Frontend State Management | React hooks + Taro storage；尚无复杂跨页响应式 store；非核心 | Zustand、Redux Toolkit（均 MIT，活跃） | React 可用，但微信 bundle/生命周期仍需验证 | 中 / 当前几乎不减代码 / 新全局状态和持久化一致性 | **KEEP_CURRENT** |
| 17 | Forms / Validation | 页面内 controlled state + 简单显式校验；后端 Pydantic 是最终契约 | React Hook Form、Zod（均 MIT，活跃） | Web React 成熟；Taro/微信事件模型、体积和现有 JS 需 PoC | 中 / 仅复杂表单有收益 / 双端 schema 与适配代码 | **KEEP_CURRENT** |
| 18 | Testing | pytest/httpx、契约脚本、构建、`miniprogram-automator`；质量基础设施 | pytest（MIT）、httpx（BSD-3-Clause）、微信自动化工具（已采用） | Python 3.12 和微信构建已通过完整基线 | 低（继续补测）/ 不需替换 / 真机自动化仍有环境成本 | **KEEP_CURRENT** |
| 19 | WebSocket Infrastructure | FastAPI/Starlette WebSocket + Taro 原生 socket；协议、重连、心跳、队列已自研并测试；实时核心 | Socket.IO（MIT，活跃）、websockets（BSD-3-Clause，活跃） | Socket.IO 不是当前裸 WebSocket 协议的无缝替换；微信客户端需新 adapter | 极高 / 可替换部分重连广播 / 协议、服务端、客户端、部署全部迁移 | **KEEP_CURRENT** |
| 20 | Game Runtime | durable state、Redis hot cache、CAS lease、恢复、隐私、结算、replay、AI；核心业务 | Colyseus（MIT，活跃）、Nakama（Apache-2.0，活跃）、boardgame.io（MIT，成熟度尚可）、Socket.IO（MIT，活跃） | 均非当前 Python + Taro 协议的直接嵌入；Nakama/Colyseus 需独立 runtime | 极高 / 可替换大量通用房间能力 / 双运行时、迁移数据与协议、运维激增 | **KEEP_CURRENT** |
| 21 | Game Rules / AI | 斗地主、象棋、斗兽棋、五子棋、飞行棋、骰子规则与 AI；产品核心 | 没有覆盖这些规则/隐私/情侣玩法的统一成熟库；`python-chess` 只适配西洋棋且 License/规则不匹配 | 通用库无法保持现有 Python/Taro 行为 | 极高 / 低 / 规则差异和回归风险 | **KEEP_CURRENT** |
| 22 | Image Processing | Pillow 验图、EXIF、格式匹配和重编码；安全基础设施 | Pillow（HPND，已采用且活跃）；libvips/sharp 不适合当前 Python 小体量路径 | Python 3.12 已验证；输出对微信透明 | 高（若换）/ 无 / 原生二进制部署复杂度 | **KEEP_CURRENT** |
| 23 | CI / Dependency Management | GitHub Actions 已覆盖完整 Gate；Dependabot 已配置 npm、pip、GitHub Actions 的周期更新与分组 | Dependabot（GitHub 托管功能；核心持续维护） | 已支持当前 pip、npm 与 Actions；不影响运行时 | 无迁移 / 已减少人工发现更新 / 后续仅可能调优 schedule、grouping 和 PR 噪音 | **KEEP_CURRENT** |
| 24 | Backup / Restore | SQLite/PostgreSQL 备份、SHA-256、row-count manifest、隔离恢复；数据安全能力 | `pg_dump`/`pg_restore`（PostgreSQL License，已采用）、数据库供应商 PITR/备份（服务条款） | 与当前 DB 栈兼容；不影响小程序 | 中 / 托管备份减少排程脚本 / 成本、保留策略、恢复演练 | **ADOPT_LATER** |

## 4. ADOPT_NOW

本节是决策，不是本轮安装授权。Round 1 的依赖新增仍为 0。

### 4.1 `pydantic-settings`

- **解决的问题**：统一环境变量类型、默认值、别名、范围与跨字段校验，消除分散读取；
- **减少的自研**：DB pool 数字截断、布尔解析、S3 缺项检查、重复 `REDIS_URL` /
  `APP_ENV` 读取可逐步集中；不删除 provider 自身的业务就绪检查；
- **新依赖**：生产依赖 `pydantic-settings`，版本必须按现有 `pydantic==2.11.4`
  求解兼容范围后固定，不能盲目使用审计日最新版；
- **风险**：集中初始化若把现有“使用时失败”误改成“进程启动即失败”，会改变生产行为；测试
  monkeypatch 环境变量也可能被单例缓存影响；
- **实施范围**：先建立兼容 Settings facade 和行为测试，再按模块替换；保持原环境变量名、默认值、
  `postgres://` 归一化、生产/local storage readiness 和 Admin credential 失败时机；
- **回滚方式**：删除 facade 与依赖，把调用点恢复到原 `os.getenv`；无 DB、API、WS 或数据回滚。

### 4.2 `import-linter`

- **解决的问题**：防止仓储反向依赖路由/通知，以及纯规则层引入 FastAPI/DB；
- **减少的自研**：不开发 AST Dependency Checker，也不靠人工逐次 grep；
- **新依赖**：仅开发依赖 `import-linter`；
- **风险**：仓库的 Python 包是多个顶层 root，若一开始写“理想架构”而非“当前绿色边界”，会产生
  大量无效豁免；
- **实施范围**：先加入少量当前应能通过的 forbidden contracts，再进 CI。首轮不强制完整
  `api > services > repositories` layers；
- **回滚方式**：移除开发依赖、配置和 CI 命令；运行时零影响。

建议首批边界语义：

1. `repositories` 禁止依赖 `api`、`services`、`notification_service`；
2. `games/*/(rule|engine|ai)` 纯规则集合禁止依赖 `fastapi`、`sqlalchemy`、`database`、`models`；
3. 不把 `games/core/room|player|state|service` 放入纯规则集合，因为它们现在明确是应用/持久化代码；
4. 后续只有在 `crud.py` 兼容导入减少后，再收紧完整 layers contract。

### 4.3 OpenTelemetry Python（可选启用）

- **解决的问题**：把 HTTP/WS 端到端慢拆成 request、DB、snapshot、lease、settlement、notification
  阶段，支持基于证据的下一轮优化；
- **减少的自研**：复用标准 context、span、FastAPI/SQLAlchemy instrumentation 与 exporter 协议，
  不自建 trace SDK；
- **新依赖**：`opentelemetry-api`、`opentelemetry-sdk`、FastAPI 和 SQLAlchemy instrumentation；
  首轮不强制 OTLP exporter；
- **风险**：错误的 span 属性可能泄露 customer/token/room/牌面，SQL instrumentation 和高采样率
  可能增加开销；contrib instrumentation 仍使用 `0.x` 版本线，需要整体锁定兼容版本；
- **实施范围**：无配置时 no-op；开发环境可用 SDK 内置 console exporter；生产 exporter 以后按环境
  显式启用。只添加观测，不改变控制流和协议；
- **回滚方式**：移除 bootstrap、manual spans、依赖与 OTel 环境变量；现有 request log 保留。

## 5. ADOPT_LATER

### 5.1 普通周期任务

Lease heartbeat 是实时正确性核心，继续留在应用进程。游戏 timeout/settlement reconciliation 也是
高频正确性修复任务，在没有单实例 worker/leader 方案前不迁出。六小时 anniversary reminder 更接近
普通任务，可在部署层稳定、付费 Cron 可接受且任务入口支持幂等后迁到 Render Cron。

APScheduler 3.11.2 是成熟方案，但简单地嵌入每个 Web worker 不能解决多实例重复执行；持久化 job
store 又会带来新的协调复杂度。Celery/RabbitMQ/Kafka 对当前规模明显过度。

### 5.2 OpenAPI 客户端生成 PoC

优先候选是 **Orval + custom mutator 调用 `Taro.request`**，其次是
`openapi-typescript` 只生成类型、保留手写 transport。OpenAPI Generator 的 TypeScript fetch 客户端
和 Java 工具链对当前微信/Taro 项目更重。

PoC 只比较三个已经进入 OpenAPI schema 的 GET：

1. `GET /api/dishes`；
2. `GET /api/orders/me`（验证 Customer Bearer）；
3. `GET /api/orders/{order_id}`（验证 path 参数与错误模型）。

`GET /api/health` 当前明确 `include_in_schema=False`，因此不能在“不改 API”的 PoC 中假装它能生成；
可把它作为手写 client 控制样本，但不能为 PoC 改后端契约。PoC 指标：生成 LOC、手写 glue LOC、
类型错误发现能力、微信构建、dist 增量、Bearer/401 行为和 diff 可读性。WebSocket 始终不在此次生成范围。

### 5.3 生产备份/PITR

保留当前脚本作为可移植备份和恢复校验。数据库供应商确定后，再选择托管备份/PITR、加密异地副本、
保留期和定期 PostgreSQL 隔离恢复演练。2026-08-10 已完成 SQLite 演练，但不能视为生产 PostgreSQL
恢复演练。

## 6. KEEP_CURRENT

### 6.1 Auth

Customer Session 的 opaque token、哈希存储、rotation、revocation 和 legacy claim 是当前私人应用的
产品语义。JWT 不会自动提供撤销和设备迁移。Admin token 虽是约 40 LOC 自研 HMAC 签名，但使用
`secrets.compare_digest`、过期、签发时间和 token version，且迁移到 JWT 会改变 token wire format。

现阶段保留。若未来变为多租户 SaaS、需要第三方身份、OIDC/social login、多个受众或跨服务验证，
再以双读过渡评估 PyJWT/Authlib/托管 IdP，而不是直接替换 Customer Session。

### 6.2 Rate Limit

当前 limiter：

- 无 Redis 时是进程内 deque 滑窗，线程锁保护；
- 有 Redis 时是共享固定窗口，key 包含时间 bucket；
- Redis 启动不可用会降级到内存；
- Customer session `8/300s`、claim/recover `5/600s`、admin login `60/300s`；
- upload `12/hour`，游戏 POST create/join 类 `30/300s`；
- HTTPException 路径返回 `429 {"detail":"操作太频繁，请稍后再试"}`，middleware 路径是
  `429` 纯文本 `Too many requests`；WebSocket lease 冲突使用 close code `4429`，不是 rate limit。

Render 当前清单是单 Web Service；配置 Redis 时多实例计数也是共享的。`limits` 是成熟后备方案，
但替换会触碰 key、窗口、失败降级和 429 契约，当前收益不足。出现多实例无 Redis、需要标准 headers、
滑动/令牌桶或策略数量明显增加时再评估。

### 6.3 Cache 与 Game State Store

`core/cache.py` 的故障边界小且明确：Redis best-effort、30 秒重连、失败退回 PostgreSQL/内存。
`game_state_store.py` 则明确 PostgreSQL 为事实来源，Redis/内存只是加速。通用 cache library 不能自动
表达“durable first + stale Redis 防复活 + 不因写缓存失败断开玩家”的语义，保留当前实现。

### 6.4 Storage 与图片处理

保留 provider abstraction 和 Pillow pipeline。R2/S3/MinIO/Supabase Storage 是部署选择，不是重写
`storage.py` 的理由。未来更换 provider 只应在现有 `StorageProvider.save` 后实现，不改 API 返回行为。

### 6.5 Logging、HTTP、Retry、前端状态/表单、测试

这些模块当前规模下均有简单、可测试的实现。Observability 接入后只把 trace/span id 注入现有日志，
不同时更换 structlog。前端继续用 Taro request、React hooks、Taro storage 和页面内校验；待出现多页
共享响应式状态或复杂动态表单再引入 Zustand/React Hook Form/Zod。

### 6.6 Database 与 Repository

SQLAlchemy/Alembic 已是成熟 OSS。继续现有函数式 repository 和 strangler：新业务不再进入 `crud.py`，
旧转发函数只在调用方迁走并有测试后删除。不要引入泛型 Repository framework，也不要在本阶段把所有
事务强行抽成一个大 Unit of Work。

### 6.7 WebSocket、Game Runtime、Rules/AI

这些是当前最成熟且最敏感的业务链路。保留裸 WebSocket 协议、Taro client 和 Python runtime；
规则/AI 继续自有实现。优先加观测与边界门禁，不先换框架。

### 6.8 Frontend UI

保留情侣视觉和现有组件：

| 基础能力 | 当前选择 | 决策 |
|---|---|---|
| Button | Taro 原生 `Button` + 自有样式 | 保留，尤其分享/禁用/accessibility 契约 |
| Card | `DishCard`、`LoveScoreCard` 等领域组件 | 保留领域视觉，不抽象万能 Card |
| Dialog / Modal | `Taro.showModal` | 保留 |
| Toast | `Taro.showToast` | 保留，可稍后统一薄封装但无需 UI 库 |
| Loading / Empty / Error | `AsyncState` | 保留并逐页复用 |
| Form | 页面内 controlled state | 保留；复杂动态表单出现后再 PoC |
| Picker | Taro 原生 `Picker` | 保留 |
| Uploader | `chooseMedia` + `uploadFile` 页面流程 | 当前仅管理菜品场景，保留 |
| Status | 页面领域状态样式 | 保留 |

TDesign Miniprogram 成熟且微信兼容，但全量引入会形成 Taro React + 原生组件双体系并改变视觉。只有未来
出现复杂、重复且当前实现明显不足的 Picker/Uploader/Dialog 时，才按单组件 PoC，不做全量换肤。

### 6.9 CI 依赖更新

Dependabot 已通过 `.github/dependabot.yml` 覆盖 npm、pip 与 GitHub Actions，并配置周期更新和分组，
因此保持当前方案。后续只在出现明确 PR 噪音或依赖家族不同步时调优 schedule/grouping；不重新引入，
也不把自动更新等同于自动合并或省略现有完整 Gate。

## 7. REJECT

下列是“当前场景拒绝”，不是对工具质量的否定：

| 方案 | 拒绝原因 |
|---|---|
| 自研 AST Dependency Checker | `import-linter` 已成熟，重复造轮子。 |
| Celery + RabbitMQ / Kafka | 当前没有吞吐、队列拓扑、独立 worker 和运维团队需求；复杂度远超收益。 |
| APScheduler 直接嵌入每个 Web worker | 不解决多实例重复执行；先保持当前幂等循环，普通任务以后用部署层 Cron。 |
| Prometheus + Grafana + Loki + Tempo/Jaeger 全栈 | 当前目标是定位阶段耗时，不是运营完整观测平台；成本和维护面过大。 |
| FastAPI Users | 官方已处于 maintenance mode，且其注册/密码/邮件模型不匹配私人设备 session。 |
| Supabase Auth 立即迁移 | 引入账户体系、供应商、schema 与 token 迁移，却不能证明当前私人应用收益。 |
| Colyseus / Nakama / boardgame.io / Socket.IO runtime 迁移 | 会替换已稳定的 Python runtime、协议、持久化和客户端；收益无法覆盖迁移风险。 |
| OpenAPI Generator 全量替换当前 client | 标准 fetch transport、Java 工具链、生成量和微信兼容尚未通过三端点 PoC。 |
| TDesign/Vant 全量替换 | 破坏现有视觉、bundle 和交互契约；重复基础控件数量不足。 |
| 新 Cache/Storage/Repository 框架 | 当前抽象短小且包含项目特有的正确性/降级语义，通用框架不能实质减少复杂度。 |

## 8. Large Module Risk Map

LOC 使用 PowerShell `Get-Content` 行数统计；修改频率是该文件在当前仓库历史中的 commit 数及最近
commit，不等同于长期年化频率。测试覆盖仅描述可定位的直接/契约/集成测试证据，仓库没有覆盖率报告，
因此不虚构百分比。

| 文件 | LOC | 主要职责数量 | 关键依赖 | 修改频率 | 测试证据 | 风险 | 是否拆 / 优先级 |
|---|---:|---:|---|---|---|---|---|
| `miniprogram/src/pages/dice/nativeScene.js` | 932 | 6：数学、shader、geometry、mesh、physics、render lifecycle | 微信 Canvas/WebGL | 1 commit；最近 2026-08-03 | smoke + game longevity 间接覆盖 | 高：平台/图形复杂，但稳定低变更 | **稍后拆，P3**；按 math/geometry/physics/render 内部拆，不换引擎 |
| `backend/game_runtime/manager.py` | 828 | 7：room、snapshot queue、restore、join/leave、dispatch、privacy payload、completion event | game state store、Gomoku AI/engine、WebSocket | 2 commits；最近 2026-08-13 | 5 个直接 runtime/WS/recovery 契约文件 + 集成测试 | 高/关键：刚稳定化，改动爆炸半径最大 | **DEFER STRUCTURAL REFACTOR，P3**；先观测，只有证据再拆 |
| `backend/schemas.py` | 736 | 8：auth、game、task/score、dish、order/review、user/notification、couple、reconnect/stats | Pydantic、`models` forward refs | 12 commits；最近 2026-08-12 | persistence、Phase2B、repository、service 及全 API response validation | 高：公共 API 契约面大 | **应拆，P2**；按域建模块并保留兼容 re-export，禁止一次性改 import |
| `backend/models.py` | 714 | 7：customer、kitchen/order、game、achievement、user/notification、couple、task/score | SQLAlchemy Base/relationships | 12 commits；最近 2026-08-12 | 至少 11 个 DB/迁移/业务集成文件 | 高：迁移与 relationship import 风险 | **可拆，P3**；只有边界稳定后用兼容 facade，收益低于 Schema/API 拆分 |
| `miniprogram/src/pages/dice/index.jsx` | 581 | 6：页面状态、AI、规则编排、触摸/动画、Canvas lifecycle、邀请/UI | Taro、React、gameLogic、nativeScene | 2 commits；最近 2026-08-03 | smoke + longevity 间接覆盖 | 中高：UI/Canvas 生命周期耦合 | **应拆，P2**；先提 hook/controller，不改变渲染与规则 |
| `miniprogram/src/api/index.js` | 566 | 7：transport、重试、auth、错误、缓存、上传、约 70 endpoint exports | Taro、env、customer storage | 14 commits；最近 2026-08-12 | session、socket、longevity、smoke、版本脚本间接/契约覆盖 | 高且高频 | **应拆，P1**；先按 domain re-export，OpenAPI 三端点 PoC 后再决定生成 |
| `backend/crud.py` | 529 | 4：兼容 facade、游戏过期、game stats、各域转发 | services、repositories、models/schemas | 15 commits；最近 2026-08-13 | 5 个直接 CRUD/service/runtime 契约文件 + API 集成 | 高但正在收缩 | **继续绞杀，P1**；不大重写，只迁调用和删除无使用转发 |
| `backend/api/routes/games.py` | 515 | 6：通用 game、flight、landlord、animal、chess、legacy dice/metadata | auth deps、services、schemas、game modules | 3 commits；最近 2026-08-12 | 10+ API/game/runtime/WS 测试文件 | 高：路由编排和游戏类型聚合 | **应拆，P2**；按 game router include，路径/operation 不变 |

`manager.py` 的当前职责确实多，但最近两次提交集中在稳定和首状态/持久化边界；此时结构拆分会让性能
问题与重构回归混在一起。先用 tracing 找热点，再决定是否只提取 snapshot pipeline 或 payload builder。

## 9. Dependency Boundary Analysis

### 9.1 当前真实边界

理想主路径已经可见：

```text
api/routes → services → repositories → SQLAlchemy/models
```

但它不是全局事实：

- `api/routes/orders.py` 等路由仍拥有通知、broadcast、memory 等跨服务编排；
- services 直接抛 FastAPI `HTTPException`，因此还不是框架无关 application layer；
- `crud.py` 同时被旧测试/旧模块依赖，并转发到新 services；
- `games/core/state.py|service.py|room.py|player.py` 直接用 SQLAlchemy/事务/HTTPException，属于
  游戏 application/persistence，不属于基础规则；
- 真正的 `games/*/rule.py`、`engine.py`、`ai.py` 主体保持纯 Python，这是应立即冻结的资产；
- repositories 没有发现反向导入 router 或 notification，这是可用 `import-linter` 固化的绿色边界。

### 9.2 目标边界

目标模块化单体方向合理，但不能用一次目录搬迁实现：

```text
backend/
  api/                       输入、认证依赖、HTTP/WS response mapping
  core/                      跨域小型基础能力（配置、观测、clock 等）
  domains/<domain>/          新增/被触达的 application + domain 代码
  infrastructure/           persistence/storage/realtime adapter
  games/                     纯规则、engine、AI（保留）
```

边界规则：

1. API 可依赖 application service；service 可依赖 repository port/implementation；反向禁止；
2. Router 负责 Request/Depends/HTTP response mapping；新/被重构的 service 逐步改用 domain exception，
   不要求本阶段全量替换现有 HTTPException；
3. Repository 不发通知、不广播、不依赖 Router；跨副作用由 application orchestration 管理；
4. 纯 game rule/engine/AI 不持有 Request、Session，不开启事务；
5. 共享 `models.py`/`schemas.py` 拆分时保留 re-export facade，避免一次改完 88 个 HTTP operation；
6. 新功能优先落到目标 domain；旧代码只在被真实需求触及时绞杀，不做空目录搬运。

### 9.3 为什么不立即整体搬目录

目录移动本身不减少依赖；它会同时制造 import、Alembic model discovery、Pydantic forward refs、测试
monkeypatch 路径和 Git history 噪音。先用 import contract 冻结边界，再以兼容 facade 逐片迁移，才符合
Strangler Refactoring。

## 10. Configuration Management Recommendation

对 `pydantic-settings` 七个问题的明确回答：

1. **是否适合当前项目？YES。** 项目已使用 Pydantic 2，配置量已超过散布 `getenv` 的舒适范围；
2. **是否能保持现有环境变量名称？YES。** 使用空 prefix、字段名或 `validation_alias`，保留
   `ADMIN_SECRET`、`DATABASE_URL`、`REDIS_URL`、S3 与 DB pool 名称；
3. **是否能保持默认值？YES。** 将现有默认值原样建模，包括本地 SQLite、pool、TTL、lease、
   upload provider、token version；
4. **是否会改变生产启动失败行为？可以不改变，但必须刻意设计。** `ADMIN_PASSWORD`、invite、
   `ADMIN_SECRET` 当前多为 endpoint 使用时失败；不能简单标成启动必填。先允许空值，在原边界调用
   `require_*`。S3 readiness 和 production local storage 的现有结果也必须保留；
5. **是否减少重复 getenv？YES。** 可集中约 29 个读取点和类型/布尔/范围解析；
6. **是否能集中校验关键配置？YES。** Admin、DB URL/Pool、Redis、S3、lease 均可分 nested settings
   或同一兼容 facade 校验；
7. **是否值得 Phase 3.0 立即采用？YES，列为 ADOPT_NOW。** 但按行为测试和小批调用点迁移，
   不是 Round 1 全面改写。

建议 Round 2 的兼容要求：

- `.env` 路径仍以 `backend/.env` 为准，不依赖当前工作目录；
- 测试可明确清空 settings cache，不能让 import 顺序吞掉 monkeypatch；
- `postgres://` 到 `postgresql://` 的归一化保持；
- 数字约束保持现有 `max` 语义：pool size ≥1、overflow ≥0、timeout ≥5、recycle ≥300、lease ≥15；
- `ALLOW_LEGACY_CUSTOMER_HEADER` 的真值集合保持；
- 禁止在配置对象 repr/log/span 中输出密码、secret、token、S3 key、DATABASE_URL credential。

## 11. Observability Recommendation

### 11.1 决策

采用可选 OpenTelemetry，但本阶段只解决“知道时间花在哪里”。不搭建 Prometheus/Grafana/Loki/
Tempo/Jaeger，不同时做性能重构。

### 11.2 最小 span 设计

| Span / 指标 | 位置 | 目的 |
|---|---|---|
| HTTP server + total latency | FastAPI instrumentation | 保留当前 request log，并获得 trace context |
| DB client latency | SQLAlchemy instrumentation | 区分连接/SQL 等待与应用耗时；不采集参数值 |
| `game.websocket.join` | WebSocket route/session service | 从连接认证到 first state 发出 |
| `game.snapshot.load` | `game_state_store.get` / restore | 区分 PostgreSQL、Redis、memory source 和耗时 |
| `game.lease.acquire` / `renew` | lease boundary | 识别 CAS/DB/竞争耗时，不记录 owner 原值 |
| `game.settlement.persist` | settlement service | 拆记录、积分、replay、ack/retry 阶段 |
| `notification.persist` | notification writer | 解释 settlement visibility 尾部耗时 |

允许的低基数字段：`game.type`、`cache.source`、`result`、`retry.count`、HTTP route template。
禁止字段：Authorization、customer token/id 原值、room code 原值、姓名、牌面/骰子、完整 payload、SQL 参数、
DATABASE_URL。

### 11.3 无 exporter 行为

- 没有 OTel 配置时不注册 SDK/export pipeline，OpenTelemetry API 走 no-op；
- 服务仍使用现有日志、正常启动、正常处理 HTTP/WS；
- 开发诊断可显式选择 SDK 内置 console exporter；
- OTLP exporter 是后续部署选择，不能成为应用启动必需；
- exporter 失败不得让请求、WebSocket join、lease heartbeat 或 settlement 失败。

### 11.4 验收方式

Round 2 只验“span 完整且业务无变化”，不承诺缩短 `4.9～9.8s` 或 `34.5s`。采集到至少一条慢
first-state 和 settlement trace 后，才进入独立性能优化提案。

## 12. Game Runtime Decision

决策：**KEEP_CURRENT**，并对 `manager.py` **DEFER STRUCTURAL REFACTOR**。

| 候选 | 成熟能力 | 与当前系统的代价 | 结论 |
|---|---|---|---|
| Colyseus | Node/TS authoritative rooms、state sync、matchmaking、reconnect | 新 Node runtime、二进制/state schema、客户端 SDK、持久化和协议迁移 | 拒绝迁移 |
| Nakama | 完整账号、社交、matchmaking、leaderboard、realtime server | 引入独立 Go server/数据库/认证体系，现有 FastAPI 与 session 价值重叠 | 拒绝迁移 |
| boardgame.io | JS turn-based engine/networking | 规则和服务器改写为 JS，微信/现有持久化与协议无直接兼容证明 | 拒绝迁移 |
| Socket.IO | 成熟重连、rooms、fallback transport | 不是裸 WebSocket wire-compatible，前后端都需换协议 | 拒绝迁移 |

当前 runtime 已有这些框架最有价值的能力，而且与私人 session、PostgreSQL durable snapshot、lease、
隐私 state shaping、幂等 settlement 和 replay 深度集成。迁移不能通过“减少 828 LOC”衡量，因为会把
复杂度移到协议 adapter、数据迁移和第二技术栈。

近期只允许：观测、缺陷修复、测试增强和在证据明确时的小型提取。禁止在 OpenTelemetry 采样前因
首状态慢而猜测性重写 manager。

## 13. Authentication Decision

决策：**KEEP_CURRENT**。

| 维度 | 私人情侣应用（当前） | 未来多用户 SaaS |
|---|---|---|
| 身份模型 | 邀请码 + 设备 Customer Session 足够 | 可能需要 email/phone/social/OIDC、tenant、MFA |
| 撤销/轮换 | DB opaque session 已直接支持 | 需集中 session/token policy、审计和风控 |
| Admin | 单一受控管理员 token | 多角色/RBAC、审计、SSO 可能必要 |
| OSS/服务收益 | 完整账户框架收益低、迁移高 | Authlib/成熟 IdP/Supabase 类服务可能变得合理 |

PyJWT 是成熟库，但它只替代 Admin HMAC 格式，不替代 Customer Session；为了“看起来标准”改 token
会造成兼容迁移而没有当前业务收益。Authlib 适合 OAuth/OIDC/JOSE，但对单 Admin 明显过重。
FastAPI Users 已进入维护模式。Supabase Auth 会引入账户/供应商模型。

安全后续项应是：为当前 Admin token 增加更明确的算法/格式契约测试、密钥轮换文档和日志脱敏；若
确需 JWT，再设计双签发/双验证窗口，绝不能直接让已上传小程序失效。

## 14. Storage Decision

决策：**KEEP_CURRENT**。

现有抽象已经覆盖三类实际部署：开发本地、S3-compatible 对象存储、小体量 PostgreSQL blob。
Pillow 会验证真实图片格式、扩展名一致性、EXIF 方向和重编码，S3 public base 还要求 HTTPS。

需要改进的是部署选择和演练，而不是 architecture：

- Render ephemeral disk 不能作为生产持久化，readiness 已标为 release-blocked；
- 当前 Render 配置选择 database provider，符合私人小体量使用；
- 数据量/流量上升后，可在同一接口后切到 R2/S3；
- MinIO 自托管会增加存储运维，不适合仅为“开源”而引入；
- Supabase Storage 只有在整体供应商/鉴权方案成立时才评估。

## 15. Frontend API Client Decision

决策：**ADOPT_LATER（仅 3 endpoint PoC）**。

当前手写 client 的价值不只是 endpoint wrapper：它还固定了 Taro transport、45s timeout、GET-only
retry、Customer Bearer、401 清 session、后端 detail 映射、version conflict 字段、菜品缓存和
`uploadFile`。任何生成方案都必须复用这些行为，不能用标准 fetch 悄悄替换。

候选对比：

| 方案 | 优点 | 主要缺口 | 排名 |
|---|---|---|---|
| Orval + custom mutator | 能从 OpenAPI 生成类型/函数，又可把 transport 接到 `Taro.request` | 引入 TS/生成配置，需验证 Taro build 和 bundle | 1 |
| openapi-typescript | 只生成类型，侵入小 | 仍要手写调用；当前项目主要是 JS，类型收益需证明 | 2 |
| OpenAPI Generator typescript-fetch | 生态和模板成熟 | Java 工具链、生成量大、默认 fetch 不等于微信 Taro | 3 |

PoC 不提交全面迁移，不动 WebSocket，不改变 API operation/path；成功也只授权按 domain 逐步生成，
并让 `src/api/index.js` 保持 compatibility re-export。

## 16. Frontend UI Decision

决策：**KEEP_CURRENT**。

仓库复用最强的是领域组件，而不是通用企业 UI。TDesign/Vant 能提供成熟复杂控件，但全量引入的主题、
交互和 bundle 成本会直接冲击情侣视觉。当前 Modal/Toast/Picker 使用 Taro 原生，Loading/Empty/Error
已有 `AsyncState`，Uploader 只有一个管理场景，尚不足以支撑 UI framework。

后续采用门槛：同一复杂控件至少出现 3 个真实重复场景、内部实现存在可访问性/兼容性缺口、单组件
PoC 通过真机/DevTools/构建体积和主题验证。满足门槛后只引入那个控件，不顺带换 Button/Card。

## 17. Proposed Phase 3.0 Actual Implementation Scope

Phase 3.0 实际工程范围建议严格限定为三个独立、可回滚的工作包：

1. **Configuration Compatibility Layer**
   - 增加 `pydantic-settings`；
   - 建立 Settings facade、脱敏 repr 和环境行为契约测试；
   - 分批替换配置读取，保持所有现有名字、默认值、失败时机；
   - 不修改 Render secret 名、不修改 API/DB。
2. **Architecture Guardrail**
   - 增加 dev-only `import-linter`；
   - 先写当前绿色 forbidden contracts；
   - 接入 CI，禁止 custom AST checker；
   - 不为让 contract 通过而整体搬目录。
3. **Optional Trace Foundation**
   - 增加 OTel API/SDK 与 FastAPI/SQLAlchemy instrumentation；
   - 无 exporter no-op，开发可 console；
   - 增加 WS join、snapshot、lease、settlement、notification 手工 spans；
   - 只采低基数、非敏感属性，不做性能行为修改。

大模块拆分、OpenAPI client PoC、Cron、Dependabot 配置调优、生产备份属于后续独立轮次，不能与这三个工作包
混在一次大 diff 中。

## 18. Explicit Non-Goals

Phase 3.0 本阶段明确不做：

- 不改游戏规则、AI 难度、UI 行为、HTTP response、WebSocket envelope/close code；
- 不改 Customer Session、Admin token 格式、数据库 schema、Alembic head；
- 不迁移 Game Runtime，不引入 Socket.IO/Colyseus/Nakama/boardgame.io；
- 不引入 Celery、RabbitMQ、Kafka，不搭全套 observability 基础设施；
- 不整体搬 `backend` 目录，不一次拆 `models.py`/`schemas.py`/`manager.py`；
- 不全量生成前端 client，不改 `Taro.request`/`uploadFile`/WebSocket transport；
- 不全量引入 TDesign/Vant/Zustand/React Hook Form；
- 不重写 Storage abstraction、Cache、Rate Limit、Repository framework；
- 不优化 4.9～9.8s/34.5s 指标，直到 tracing 提供阶段证据；
- 不提交、不 push、不 merge/rebase、不上传微信版本。

## 19. Risk

| 风险 | 概率 | 影响 | 控制措施 |
|---|---|---|---|
| Settings 改变缺失变量的失败时机 | 中 | 高 | 对每个环境变量建立旧/新行为表；required-on-use 保持 Optional + 显式 require |
| Settings 单例污染测试 | 中 | 中 | 提供唯一 cache reset fixture；禁止模块各建一个 Settings 实例 |
| import-linter 首批规则误报 | 中 | 低 | 只加入当前绿色边界；例外必须写原因和过期条件 |
| OTel 依赖版本不匹配 | 中 | 中 | API/SDK/instrumentation 同一兼容版本组固定；先 CI/本地 smoke |
| tracing 泄露敏感信息 | 低到中 | 高 | 属性 allow-list；不采 header/body/token/id/room/payload/SQL 参数；代码审查 |
| tracing 增加 latency/日志量 | 中 | 中 | 无配置 no-op；开发低采样；生产 exporter 后配采样与批处理 |
| 为了过 import contract 顺带大重构 | 中 | 高 | Round 2 diff 预算和 non-goals；先守现状而非理想层级 |
| 大模块拆分与性能问题互相干扰 | 中 | 高 | manager 延后；先 trace 后单独提案 |
| OSS 活跃度/License 后续变化 | 低 | 中 | 采用前再次核验固定版本、LICENSE、changelog 和安全公告 |

## 20. Rollback Strategy

三个 `ADOPT_NOW` 必须保持互不依赖、可逐个回滚：

1. **Settings**：保留调用点前后的行为测试；回滚 facade 和依赖即恢复原 `getenv`。环境变量名不改，
   因此无需改 Render 或本地 secret；
2. **Import Linter**：移除 CI step、配置与 dev dependency 即完成回滚；不影响产物；
3. **OpenTelemetry**：移除 bootstrap/manual span 和依赖，清理 OTel env；现有 logging 与 request id
   始终保留，应用无 exporter 时本就可正常运行。

任何实现轮次出现以下一项即停止，不继续下一工作包：现有 API/WS snapshot 变化、Customer Session
行为变化、Migration 生成、游戏契约失败、无 exporter 无法启动、敏感字段出现在日志/span、完整基线
Gate 任一失败。

## 21. Recommended Round 2

建议 Round 2 名称：**Phase 3.0-R2 — Guardrails & Trace Foundation**。

按三个可独立评审的阶段执行：

1. `pydantic-settings` compatibility facade + 行为测试；先迁低风险 typed/default 配置，再迁 secret
   引用，逐步跑基线；
2. `import-linter` dev dependency + 2～3 个当前绿色 contract + CI；不修理与 contract 无关的结构；
3. OTel optional bootstrap + HTTP/DB 自动 instrumentation + 五个关键 manual spans；无 exporter smoke、
   隐私检查、开销检查。

Round 2 成功门槛仍应包括当前完整 Gate，并额外验证：

- 现有环境变量名称、默认值和失败时机全部一致；
- `lint-imports` 在 Windows 与 CI 通过；
- unset OTel exporter 时应用和测试完全正常；
- console exporter 能看到一条 request、一条 WS join 和一条 settlement 的阶段树；
- trace/log 中没有 token、secret、姓名、room code、牌面/骰子或 payload；
- HTTP operations 仍为 88、WebSocket paths 仍为 3、Alembic head 仍为 `20260812_12`；
- 不产生数据库 Migration，不修改小程序协议/业务/UI。

完成 Round 2 后仍需人工审查；不得自动进入大模块拆分或性能优化。

## 22. Sources and Audit Evidence

主要官方/一手资料（访问并核验于 2026-08-14）：

- [Pydantic Settings 文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)；
  [PyPI 项目元数据](https://pypi.org/project/pydantic-settings/)
- [Import Linter 文档](https://import-linter.readthedocs.io/en/stable/)；
  [PyPI 版本与 License](https://pypi.org/project/import-linter/)
- [OpenTelemetry Python](https://github.com/open-telemetry/opentelemetry-python)；
  [Python SDK PyPI](https://pypi.org/project/opentelemetry-sdk/)；
  [FastAPI instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)；
  [SQLAlchemy instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/sqlalchemy/sqlalchemy.html)；
  [SDK 环境变量规范](https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/)
- [`limits` PyPI](https://pypi.org/project/limits/)；
  [SlowAPI](https://github.com/laurentS/slowapi)
- [APScheduler](https://github.com/agronholm/apscheduler)；
  [Render Cron Jobs](https://render.com/docs/cronjobs)
- [Taro.request](https://docs.taro.zone/en/docs/apis/network/request/)；
  [Orval custom client](https://orval.dev/docs/guides/custom-client/)；
  [OpenAPI Generator](https://github.com/OpenAPITools/openapi-generator)；
  [openapi-typescript](https://github.com/openapi-ts/openapi-typescript)
- [PyJWT](https://github.com/jpadilla/pyjwt)；
  [FastAPI Users maintenance notice](https://fastapi-users.github.io/)
- [TDesign Miniprogram](https://github.com/Tencent/tdesign-miniprogram)
- [Colyseus](https://github.com/colyseus/colyseus)；
  [Nakama](https://github.com/heroiclabs/nakama)；
  [boardgame.io](https://github.com/boardgameio/boardgame.io)；
  [Socket.IO](https://github.com/socketio/socket.io)
- [Dependabot 配置参考](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)

仓库证据包括本报告列出的重点模块、全部 `>500 LOC` 源文件、依赖清单、Render/CI 配置、测试引用、
最近 10 个 Git commit、环境变量读取点和现有备份/恢复文档。报告未安装候选包，也未运行会写入生产
或外部系统的命令。
