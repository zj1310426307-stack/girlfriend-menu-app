# Continuous Optimization 03 验证报告

- 验证日期：2026-08-24
- 分支：`feature/continuous-optimization-03`
- 结论：PR 自有 CI、小程序全量测试/确定性构建/产物完整性与开发者工具普通模式通过；隔离 staging 因数据库认证失败未就绪，体验版/真机和 production 未执行

## 1. 变更范围

- GitHub Actions backend job 增加 PostgreSQL 18 临时 service 与六个迁移步骤。
- 新增 staging 只读 readiness 工具及 20 项失败关闭/状态合同测试。
- 小程序新增可选 API 能力冷却、游戏 GET 单次请求预算和菜单滚动容器兼容修复。
- 开发者工具验收增加完整 storage 快照/恢复、旧固定哨兵迁移和产物模块完整性检查。
- 同步 backlog、当前架构、部署、监控、微信清单和本轮交付材料。
- 无业务 API、OpenAPI、数据库 revision、生产依赖或云资源变化。

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

CI YAML 已通过本地解析，源码合同确认 `postgres:18-alpine` 和六个 PostgreSQL 命令存在。候选推送后的 PR #21 backend job 已通过，远端 PostgreSQL 18 与 SQLite 双矩阵获得实际执行证据。

## 5. 小程序与包体

- `npm run test:ci`：PASS。
- `npm run build:weapp`：PASS，Taro 4.2.0。
- 主包：57 files / 470,867 B。
- 总产物：182 files / 890,679 B。
- `npm run test:dist`：PASS，71 个 JavaScript 文件、140 个模块定义，无缺失数字模块引用。

新增能力冷却使主包较上一候选增加 1,829 B、总产物增加 1,853 B，仍低于既有预算。为避免 Taro 4.2 持久化缓存产生跨主包/分包的陈旧模块编号，候选构建关闭该本地构建缓存；这只影响开发构建耗时，不影响小程序用户启动路径。未配置独立 Origin 的 staging 构建继续失败关闭；没有用生产 Origin 生成 staging 包。

## 6. 真实本地启动与隐私

使用独立临时 SQLite 和显式合成测试凭据启动 `serve.py`：

- migration/seed 完成，Uvicorn application startup complete；
- `/api/health` 返回 ok，`/api/ready` 返回 ready；
- authentication/storage ready，微信 optional-disabled；
- 动态房间请求返回 404，日志只记录 `/api/games/rooms/{room_code}`，不含 sentinel 原文；
- 进程停止后临时数据库已删除。

## 7. 发布安全门

- `check_release_config.py`：PASS，三套 Blueprint 保持 free + manual deploy。
- `check_secrets.py`：PASS；本轮最终文件数见提交前复验结果。
- `git diff --check`：PASS。
- 无新依赖、无付费资源、无生产部署、无业务数据写入。

## 8. 外部状态核对

- GitHub：候选已推送并创建 PR #21；backend、miniprogram、release-safety 和 Vercel Preview Comments 通过。额外的 Vercel Preview 部署失败，但该仓库已不含网页前端，Vercel 不是当前微信小程序 + Render 后端的交付路径。
- Render：已登录并只读核对现有独立免费 staging service。staging 与 production 的数据库目标不同，`APP_ENV=staging`、`UPLOAD_PROVIDER=database`；未修改 production。staging 冷启动在 PostgreSQL 认证阶段失败，health/readiness 尚未通过。
- Neon：已登录免费账户；当前控制台只看到一个既有项目的 production 分支。未创建项目/分支、未重置密码、未复制连接串。官方免费计划允许独立项目，因此下一步优先新建空 staging 项目，而不是从 production 分支复制数据。
- 微信：开发者工具服务端口已开启，CLI `islogin` 返回 `login:true`。普通调试模式最终显示业务错误 0；原 `/bootstrap`、`/customers/wechat-session` 重复 404、游戏 GET 重复 502、菜单 `scroll-view` padding 和缺失分包模块均不再出现。DevTools 3.15.2 自动化服务自身仍可能出现 timeout/资源 preload 提示；该结果不代表预览码、体验版或真机对局通过。

2026-08-24 的只读 production 复核中，`/api/health` 与 `/api/games` 在 20 秒内未响应，`/api/games/active` 无凭据时返回预期 401，`/api/bootstrap` 返回 404。该证据说明截图中的 502/404 主要来自免费 Render 当前可用性与旧服务能力；客户端只负责快速离线降级和避免重复请求，不能把真实服务故障伪装成成功。

当前状态是“免费交付门和开发者工具候选通过、隔离 staging 数据库待修复、真机待验收”，不是已上线或 production 就绪。

## 9. 微信开发者工具稳定化补充

首次自动验收暴露两个测试基础设施问题并已修复：

1. 脚本曾把固定 `--port` 作为 IDE service 端口传入，覆盖开发者工具自动发现结果，导致 automator 无法启动；现仅显式传递自动化 WebSocket 端口。
2. 模拟器残留的过期会话可能被首页异步清理，首次进入保护页面会回到首页；现清理测试过期标记，并且只对明确回到首页的场景重写隔离会话后重试一次，其他重定向继续失败关闭。

新增零依赖 CI 合同测试防止固定 service port 回归。最终结果：`npm run test:ci` PASS，`npm run test:game-pages:devtools` PASS，四张候选截图生成成功。

随后针对用户控制台截图补充修复：

1. 按 API Origin 隔离记录 6 小时能力冷却，后台启动不再重复探测旧服务缺失接口；主动邀请码登录仍即时探测并保留兼容回退。
2. 游戏大厅两个可离线降级的 GET 关闭同请求自动重试，避免每个 502 重复两次并缩短离线首屏等待。
3. 菜单分类按钮移入 `v2-category-tabs-track`，`scroll-view` 自身不再承载按钮 padding。
4. 自动验收完整备份/恢复模拟器 storage，并精确迁移旧版固定哨兵会话，失败路径同样恢复。
5. Taro 文件缓存曾让 `gameRecovery` 分包引用未生成的模块 `645`；清除生成物后无缓存全量构建改为正确模块 `4324`，新增 `test:dist` 防止再次生成缺失模块引用。

最新结果：`npm run test:ci` PASS；`npm run build:weapp` PASS；`npm run test:dist` PASS。普通模式错误数为 0。自动化模式复跑受到开发者工具 `WAAutoService/WAServiceMainContext` 内部超时影响，未把该工具内部失败误记为应用验收通过。

## 10. 剩余风险

- PostgreSQL JSONB、表锁和 downgrade 行为必须由远端 CI 与隔离 staging 实测确认。
- 免费 Render 冷启动、跨区域 RTT 和微信真实网络启动 P95 仍无新证据。
- staging PostgreSQL 当前凭据不可用；在新建独立空 Neon staging 项目并更新 Render staging secret 前，不得部署候选或生成 staging 小程序包。
- Vercel Preview 红项会污染 PR 汇总；由于没有网页交付物，应在确认后断开该旧项目的 Git 集成，而不是为无用网页预览增加运行时代码。
- DevTools 3.15.2 自动化服务存在内部超时与未使用 preload 提示；普通模式不应为消除工具内部提示而修改业务代码，自动化复跑仍需失败关闭并保留普通模式/真机证据。
- 跨实例附属动作严格不丢不重仍需 transactional outbox/effect ledger。
- 房间 lease fencing、全局 scheduler ownership、参考数据版本标记仍在 backlog。
