# LoveOS V3 Continuous Optimization 01 验证报告

- 验证日期：2026-08-24
- 分支：`feature/continuous-optimization-01`
- 环境：Windows / PowerShell，Python 3.12.13，Node.js 24.17.0，npm 11.13.0，Git 2.55.0
- 数据边界：所有数据库测试使用 suite-owned 或显式临时 SQLite；临时数据库已清理；未连接生产、staging、Neon、微信或 S3

## 1. 结论

本轮本地自动化闭环通过。后端 236 项测试、小程序生产构建与全套 CI、架构约束、OpenAPI/schema 快照、迁移链、启动健康检查和发布安全门均通过；没有测试失败。

可复现的性能结果是“写入预算”而不是推测百分比：最近 5 分钟内活跃的 session 认证不产生 `customers`/`customer_sessions` UPDATE，也不 commit；过窗后一个请求取得条件更新 ownership，竞争请求不重复推进窗口。

本报告只证明本地候选。PostgreSQL staging、微信体验版/真机、托管冷启动、备份恢复和跨实例一致性仍未验证。

## 2. 依赖与构建

| 命令 | 结果 | 备注 |
| --- | --- | --- |
| `cd miniprogram && npm ci --ignore-scripts` | PASS | 干净安装 1224 packages；出现既有 deprecated transitive dependency 警告，无安装错误 |
| `npm ls @babel/plugin-transform-modules-commonjs --depth=0` | PASS | 行为测试使用的直接 dev dependency 为 7.29.7 |
| `npm run build:weapp` | PASS | Taro 4.2 / Webpack 编译成功；冷 node_modules 构建约 1.11 分钟 |

项目没有 TypeScript 或 mypy/pyright 配置，因此没有可执行的独立静态类型检查命令。Python 由 Pydantic/pytest 覆盖，JavaScript 由生产构建与合同/行为测试覆盖；这不等同于完整类型系统，已列入后续 backlog。

项目没有 Dockerfile 或 Docker 部署链，因此 Docker build 不适用。

## 3. 后端质量门

| 命令 | 结果 |
| --- | --- |
| `cd backend && .venv\Scripts\python.exe -m pytest -q` | PASS：236 passed，11 warnings，54.01 s |
| `.venv\Scripts\python.exe -m ruff check . ..\scripts` | PASS |
| `.venv\Scripts\lint-imports.exe` | PASS：128 files、408 dependencies、5 contracts kept |
| `.venv\Scripts\python.exe -m compileall -q .` | PASS |
| `backend\.venv\Scripts\python.exe scripts\export_v3_schema.py --check` | PASS：`database/v3-schema.sql is current` |
| `backend\.venv\Scripts\python.exe scripts\export_openapi.py --check` | PASS：`openapi-v3.json is current` |

11 条 warning 全部来自 Python 3.12 SQLite 默认 datetime adapter 的既有弃用提示；本轮没有新增测试失败，但该兼容清理应在后续排期。

## 4. 本轮定向行为验证

### 4.1 认证 activity

`backend/tests/test_customer_activity_throttle.py` 共 8 项行为覆盖，已包含在 236 项全量测试中：

- 热 session：零 UPDATE、零 commit，时间戳不变化。
- stale session：首次同步更新 session/customer，紧随请求进入冷却。
- 两个 stale SQLAlchemy Session 视图：只有一个提交，第二个不能覆盖窗口。
- 首次读取后账号被另一事务停用：session touch 回滚，请求返回 401。
- revoked、expired、inactive：逐请求继续拒绝。
- expired session：保持原语义，写入 revoked 时间。
- `update_last_seen=False`：即使 stale 也不写。

相关既有 customer session、bootstrap、router 定向回归与新增测试在实施阶段合计 21 passed；随后全量 236 passed。

### 4.2 客户本地状态隔离

`npm run test:session` 实际转换并执行生产源模块，使用 Taro storage/socket mock，不只是正则检查。结果：

- 客户 A 的 cart、repeat draft、reconnect 和 room-session secret 在退出/owner 切换后不可由 B 读取。
- 同 owner token 刷新保留购物车和快照。
- 新 reconnect key 同时绑定 customerId 和 roomCode，owner/room 分隔无歧义。
- 旧无 owner reconnect token 只删除、不读取。
- 清理可重复执行；一个 remove 抛错不阻断其余 bearer/草稿清理。
- `gf_customer_id` 和公共 `gf_dishes_cache_v28` 保留。
- WebSocket `session` 事件继续传给页面，但 secret 不再落盘。

## 5. 小程序回归

执行 `npm run test:ci`，全部通过：

- 斗地主横屏配置与牌桌合同。
- 游戏长时运行 UI/recovery 合同。
- WebSocket reconnect/queue 生命周期。
- customer session 源码合同与 session-owned storage 行为测试。
- V3 bootstrap 架构合同。
- 核心产品流程合同。
- 首页 warm-launch/cache/loading 合同。
- Tab warm-launch/cache/request ownership 合同。

生产构建后包体：

| 范围 | 大小 |
| --- | ---: |
| 主包 | 469,038 B |
| 20 个分包合计 | 419,788 B |
| 总产物 | 888,826 B |
| 最大单分包 | `pages/dice-online`：49,150 B |

主包较审计前记录的 467,041 B 增加 1,997 B，来自本轮 storage 隔离与测试所需运行代码，但仍远低于微信限制和现有预算。没有据此编造真实网络首屏提速比例。

## 6. 数据库迁移

使用两个显式临时 SQLite 数据库执行并在验证后删除：

1. 空库 `alembic upgrade head`：PASS，线性升级到 `20260817_14`。
2. 同一空库 `alembic downgrade -1`：PASS，回到 `20260817_13`。
3. 再次 `alembic upgrade head`：PASS。
4. 独立库先 `upgrade 20260808_01`，再 `upgrade head`：PASS。

本轮没有新增 migration；上述验证覆盖工作区一并交付的既有 V3 migration 链。PostgreSQL 方言、锁和真实恢复仍需隔离 staging 验收。

## 7. 启动与性能预算

### 7.1 真实启动 smoke

- 使用显式临时 SQLite 和 `PORT=8765` 运行 `backend/.venv/Scripts/python.exe serve.py`。
- Uvicorn 完成 application startup。
- `GET http://127.0.0.1:8765/api/health` 返回 200：`{"status":"ok","service":"girlfriend-menu-api"}`。
- 验证后主动停止本地进程并删除临时数据库；停止动作导致承载 shell 的退出码非 0，不是应用启动失败。

### 7.2 免费启动路径

在同一全新临时数据库连续执行 `prepare_free_runtime()`：

- 首次：migration + reference seed，`total_ms=1334.6`，其中 seed `67.6 ms`。
- 第二次：schema/reference 都无需修改，`total_ms=3.2`。

结果仅代表本机 SQLite，不代表 Render/Neon 托管唤醒延迟。

### 7.3 本地性能预算

`scripts/benchmark_v3.py` 使用 local TestClient + isolated SQLite：

| 指标 | mean | p95 | 预算 |
| --- | ---: | ---: | ---: |
| bootstrap | 10.211 ms | 11.781 ms | ordinary API 300 ms |
| legacy five requests | 23.675 ms | 26.600 ms | 对照样本 |
| gomoku strategy AI | 0.118 ms | 0.089 ms | 100 ms |
| room creation | 0.005 ms | 0.006 ms | 300 ms |
| reconnect snapshot | 0.013 ms | 0.014 ms | 3000 ms |
| replay serialization | 0.012 ms | 0.014 ms | 1000 ms |

所有脚本预算通过；这些微基准不外推为真机或公网百分比。

## 8. 发布与秘密门

| 命令 / 场景 | 结果 |
| --- | --- |
| `scripts/check_release_config.py` | PASS；production/staging/Oregon 均 free + manual deploy |
| `scripts/check_secrets.py` | PASS；扫描 487 个 release-candidate files |
| 逻辑备份缺 3 个必填 env | 预期失败；网络前退出并列出全部缺失项 |
| 逻辑备份使用 HTTP origin | 预期失败；网络前拒绝非 HTTPS |
| `git diff --check` | PASS；只有 Windows LF→CRLF 提示，无 whitespace error |

## 9. 核心场景覆盖映射

| 场景 | 本地证据 | 状态 |
| --- | --- | --- |
| 正常启动/进入 | `serve.py` + `/api/health`；bootstrap tests | 通过 |
| 登录、刷新、退出、过期 | customer session/API tests；storage behavior | 通过 |
| 核心数据增查改 | 订单、评价、任务、收藏、管理 API tests | 通过 |
| 页面刷新后数据保持 | home/tab snapshot contracts | 通过（代码/模拟） |
| 网络异常/超时/401 | transport、bootstrap、startup tests | 通过（模拟） |
| 空数据/非法输入/权限不足 | 全量 API tests | 通过 |
| 重复提交 | order mutation/submission safety tests | 通过 |
| 数据库迁移 | empty/down/up/from-V2 | 通过（SQLite） |
| 生产构建 | Taro WeApp build | 通过 |
| 真机布局/触控/读屏 | 无真机自动化证据 | 未验证 |
| PostgreSQL/S3/微信真实凭据 | 未访问外部服务 | 未验证 |

## 10. 未验证与限制

- 未运行 GitHub 远端 CI；本地结果需由提交后的远端候选复核。
- 未执行 Render staging/production 部署，未产生费用。
- 未执行 Neon PostgreSQL migration/restore、S3 上传或 Redis 多实例验证。
- 未进行微信体验版、真机视觉、弱网、真实微信身份和两设备在线游戏验收。
- 未验证 outbox/effect ledger 或 lease epoch fencing；当前仍不能承诺跨实例副作用严格不丢不重。
- npm 干净安装暴露多项传递依赖 deprecated 警告；本轮未为消除警告而高风险升级 Taro 工具链。
