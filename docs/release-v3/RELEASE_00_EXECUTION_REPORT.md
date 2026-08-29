# LOVEOS-RELEASE-00 执行报告

更新日期：2026-08-29

## 当前结论

**GATE 00-03 PASS — GATE 04 IN PROGRESS — NO MERGE / NO PRODUCTION CHANGE**

候选分支和 PR 已冻结核验，本地完整回归、迁移、契约、构建、密钥扫描与远端必需 CI 均通过。独立 Neon Free staging 项目和 Render Free staging 服务已建立，冻结候选 `d11a708` 首次部署成功，hosted health/readiness 只读门及带邀请码的 HTTP/WebSocket 写链路均通过。Gate 04 仍缺真实微信凭据、OpenID 绑定和微信真机证据；本轮尚未合并 PR、未迁移或部署生产、未创建 Tag/Release。

## Gate 00：候选冻结

| 项目 | 结果 |
| --- | --- |
| 仓库 | `zj1310426307-stack/girlfriend-menu-app` |
| 分支 | `feature/continuous-optimization-03` |
| 代码候选提交 | `d11a708a6cf1fc9b807e734ee111670ce674625d` |
| 发布证据修订 | 包含本报告的当前 PR head；推送后从 GitHub 实时核对 |
| 基线 `main` | `641c0d612d2c5b77e731e43271e0b6462fdb52b9` |
| PR | [#21](https://github.com/zj1310426307-stack/girlfriend-menu-app/pull/21)；OPEN、非 Draft、MERGEABLE |
| 审查线程 | 0 个未解决且未过期线程 |
| 工作区 | 核验时干净，分支与远端 head 一致 |

## Gate 01：本地发布候选验证

- 后端依赖：`requirements-dev.txt` 已按现有虚拟环境校准，无依赖漂移。
- 后端测试：`275 passed`；11 条 Python 3.12 SQLite datetime adapter 弃用警告。
- 质量门：Ruff 通过；Import Linter 5/5 契约通过；compileall 通过。
- 契约门：V3 schema 与 OpenAPI 导出均为 current。
- 安全门：514 个候选文件密钥扫描通过；发布配置检查通过。
- SQLite 迁移：空库升至 `20260817_14`；降至 `20260817_13` 后再升 head；V2 `20260808_01` 升 head，全部通过。
- PostgreSQL：本机没有 Docker、psql 或 pg_dump；PR backend job 已在 PostgreSQL 18 服务上通过同等迁移矩阵。
- 性能基线：bootstrap p95 43.150 ms；旧五请求 p95 88.698 ms；本地 AI p95 0.399 ms；建房 p95 0.027 ms；重连 p95 0.071 ms；回放 p95 0.069 ms。
- 小程序：`npm ci`、生产构建、`test:ci`、dist 完整性全部通过；71 个 JS 文件、140 个模块。
- 包体：主包 57 文件 / 470,867 B；总包 182 文件 / 890,679 B。

Windows 沙箱首次执行时，历史 `.test-tmp` ACL 和 `dist` 写权限导致基础设施级失败。旧临时目录已整体保留在忽略目录 `.pytest-tmp/acl-quarantine-20260828`，随后以仓库自带 Windows 隔离入口重跑，业务测试与构建均真实通过；初次失败不计为产品回归。

## Gate 02：PR 与 CI

- `backend`：PASS。
- `miniprogram`：PASS。
- `release-safety`：PASS。
- `Vercel Preview Comments`：PASS。
- `Vercel`：FAIL，按任务书为非阻断；本项目生产 API 仍以 Render 为发布目标。

以上应用候选对应 `d11a708`，同一提交已部署到隔离 staging。其后的 staging Origin 与证据修订也必须在各自成为 PR head 后重新通过 CI，不能复用旧结论冒充新提交通过。

## Gate 03：staging 隔离审计

- Neon：新建独立 Free 项目 `loveos-staging-release-00`，项目 ID `long-river-71712327`，AWS 新加坡、PostgreSQL 18；创建时存储为 0，未复制现有项目数据。
- Render：新建 Free 服务 `girlfriend-menu-api-staging`，新加坡区域，来源提交 `d11a708`；首次部署成功且健康检查日志持续返回 200。
- `miniprogram/.env.staging`：指向 `https://girlfriend-menu-api-staging.onrender.com`，与生产 Origin 分离。
- 只读 hosted 门：`/api/health` 200；`/api/ready` 为 `ready`，PostgreSQL、database storage、authentication 均 ready；Redis 和微信登录按 staging 第一阶段保持 optional-disabled。
- 未认证 `/api/bootstrap` 返回 401，符合设备会话边界。

Gate 03 当前为 **PASS**。Gate 04 的 hosted 业务子门已通过：客户会话/bootstrap、存量认领与换机恢复、菜单收藏、管理认证与 WebSocket、持久图片、订单状态/评价/撤回，以及双客户端游戏 WebSocket/重连全部成功。凭据在诊断输出风险后完成二次轮换，并用一次性 RSA 加密交接复验；仓库和验收输出未保存明文。真实微信凭据、OpenID 绑定和真机验收仍未完成，因此不得合并或进入生产门禁。

2026-08-29 的微信开发者工具复验已排除自动化端口冲突：无凭据的系统信息与清缓存探测通过。staging 业务请求随后被微信客户端以 `MINIPROGRAM_DOMAIN_NOT_ALLOWED` 拒绝，未到达 Render；因此 Gate 04 当前新增明确阻塞项“公众平台 request 合法域名未对当前 AppID 生效”。本结果不得记为应用通过或真机通过。

## 依赖安全观察

`npm audit --omit=dev` 报告 17 个生产依赖树公告（11 moderate、3 high、3 critical）。critical 链路主要来自 Taro 4 的 H5 `swiper` 依赖；源码和微信 dist 均未引用 swiper，微信产物也不分发 `node_modules`。npm 给出的自动修复会把 Taro 4 降为 3.x，属于破坏性大版本替换，因此不在发布闭环中强制执行。该项记录为后续 Taro 官方兼容升级专项，不删除、不隐瞒。

## 当前禁止动作

- 不合并 PR #21。
- 不对生产数据库执行迁移或写入。
- 不部署或切换生产服务。
- 不创建 `v3.0.0` Tag/GitHub Release。
- 不把开发工具自动化超时写成微信真机通过。
