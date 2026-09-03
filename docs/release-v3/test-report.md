# LoveOS V3 本地测试报告

验证更新日期：2026-08-23
环境：Windows，本地隔离 SQLite，Taro WeApp 生产构建；不代表托管环境或真机性能。

## 后端

| 门禁 | 结果 |
| --- | --- |
| Ruff | PASS |
| pytest | PASS，228 passed / 11 existing SQLite datetime deprecation warnings |
| compileall | PASS |
| Import Linter | PASS，128 files / 408 dependencies / 5 contracts |
| OpenAPI 快照 | PASS |
| PostgreSQL schema 快照 | PASS |
| 密钥扫描 | PASS，480 release-candidate files |
| 发布配置静态检查 | PASS |
| 免费启动冒烟 | PASS，首次迁移/种子约 1.388 秒，重复唤醒快路径约 5.0ms，单进程 `/api/health` 200 |
| Alembic | 沿用已通过的隔离库 upgrade/downgrade/upgrade 证据，head `20260817_14` |

## 性能

| 场景 | p95 |
| --- | ---: |
| `/api/bootstrap` 五项聚合 | 21.270 ms |
| 旧五请求首屏 | 74.468 ms |
| 五子棋策略 AI | 0.110 ms |
| 房间创建 | 0.006 ms |
| 重连快照恢复 | 0.016 ms |
| 回放序列化 | 0.012 ms |

所有本地预算通过。菜单本地缓存命中不发网络请求；首屏聚合显著少于 1 秒目标，但正式结论仍需 hosted + 真机证据。

## 小程序

| 门禁 | 结果 |
| --- | --- |
| `build:weapp` | PASS（最终重复生产构建 10.03 秒） |
| `test:ci` | PASS（含首页/四个一级页缓存隔离、请求所有权、弱网预算和分包契约，2026-08-23） |
| `test:games` | PASS |
| `test:landlord` | PASS |
| 主包 | 467,041 bytes / 0.445 MiB |
| 分包 | 420,844 bytes；20 个分包 |
| 全部构建产物 | 887,885 bytes / 0.847 MiB |

本轮在前端登录兼容和首页导航之外，还收紧了管理密码轮换事务、微信上游响应校验、下单成功确认、收藏并发、订单终态语义、管理端请求所有权，以及状态更新、撤回和评价的提交后可靠性。新增回归直接覆盖两个管理端陈旧状态冲突、附属动作失败后主结果如实成功、同状态/同评价补偿和撤回重试不反向翻转。2026-08-21 又加入 staging 隔离门：专用 Blueprint 关闭自动部署，staging 小程序禁止指向生产 API，未配置独立 HTTPS Origin 时构建明确失败；生产构建、完整小程序 CI、密钥扫描、发布配置和 `git diff --check` 均重新通过。迁移和性能代码未在本批继续修改，沿用此前已通过的隔离 Alembic upgrade/downgrade/upgrade 与性能预算证据。

2026-08-23 的启动优化加入按客户隔离的首页与四个一级页快照；复访首帧先使用本地内容，网络只做后台更新。各页刷新具有单一请求所有权和成功冷却，GET 等待和重试预算已收紧，首页超时不再展开五接口，列表图片按用途缩小。微信启用按需组件注入，并将五个非首屏页面移入分包。相对 488,022 bytes 基线主包，本轮仍减少 20,981 bytes（4.30%）；相对只优化首页的 458,780 bytes 增加 8,261 bytes，用于四页快照、同步提示、冷却和契约保护。真机可交互 P95 仍必须在隔离 staging 体验版上采集，不能用本地构建或 API 数据代替。

托管启动候选已切换为纯免费路径：production/staging/Oregon 三个 Blueprint 都使用 `plan: free` 与单进程 `python serve.py`。普通唤醒只执行一次数据库就绪查询；首次部署或漂移时才迁移和种子。客户端网络超时不再展开旧五接口，四个一级页也增加成功刷新冷却。所有云端配置仍未应用。

2026-08-24 第三轮补充免费 PostgreSQL 交付门与 staging 只读入口：backend workflow 已配置 PostgreSQL 18 service，覆盖 upgrade/down/up 与 from-V2，并保留 SQLite 矩阵；20 项定向门禁和 272 项后端全量测试通过，小程序 CI/生产构建继续通过，主包 469,038 bytes、总产物 888,826 bytes。当前候选未推送，本机也没有可运行的 PostgreSQL 容器，因此这里只证明 workflow 配置与合同，远端 PostgreSQL job 仍待验收。Render 未登录、微信开发者工具配置未初始化，未部署 staging 或生成真机证据。

2026-08-28 独立 Neon/Render Free staging 已部署候选 `d11a708`。只读 readiness 与 8 域带邀请码业务写链路均通过，覆盖客户会话/恢复、菜单收藏、管理认证、持久图片、订单/评价/撤回，以及管理和双客户端游戏 WebSocket/重连。凭据轮换后的复验通过一次性 RSA 密文交接执行；新增 3 项安全门回归后，后端全量为 275 passed、11 个既有 SQLite datetime adapter 警告。真实微信 code2Session、OpenID 绑定、开发工具交互和真机性能仍待验收。

## 契约基线

- HTTP `/api/*` operations：89。
- WebSocket routes：3。
- Alembic head：`20260817_14`。
- code2Session 测试完全 mock，不向微信发送测试请求。
