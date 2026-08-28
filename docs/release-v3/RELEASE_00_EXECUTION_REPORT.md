# LOVEOS-RELEASE-00 执行报告

更新日期：2026-08-28

## 当前结论

**GATE 00-02 PASS — GATE 03 BLOCKED — NO MERGE / NO PRODUCTION CHANGE**

候选分支和 PR 已冻结核验，本地完整回归、迁移、契约、构建、密钥扫描与远端必需 CI 均通过。Neon 免费组织当前只有一个项目且该项目只有一个分支，仓库的 staging Origin 也尚未配置，因此没有证据证明存在隔离 staging 数据库。按照发布门禁，本轮尚未合并 PR、未迁移或部署生产、未创建 Tag/Release，也不能宣称微信真机通过。

## Gate 00：候选冻结

| 项目 | 结果 |
| --- | --- |
| 仓库 | `zj1310426307-stack/girlfriend-menu-app` |
| 分支 | `feature/continuous-optimization-03` |
| 代码候选提交 | `ed8f2dcaf54c24e4c66fa8f72ba12d9cf737880a` |
| 发布证据修订 | 包含本报告的当前 PR head；推送后从 GitHub 实时核对 |
| 基线 `main` | `641c0d612d2c5b77e731e43271e0b6462fdb52b9` |
| PR | [#21](https://github.com/zj1310426307-stack/girlfriend-menu-app/pull/21)；OPEN、非 Draft、MERGEABLE |
| 审查线程 | 0 个未解决且未过期线程 |
| 工作区 | 核验时干净，分支与远端 head 一致 |

## Gate 01：本地发布候选验证

- 后端依赖：`requirements-dev.txt` 已按现有虚拟环境校准，无依赖漂移。
- 后端测试：`272 passed`；11 条 Python 3.12 SQLite datetime adapter 弃用警告。
- 质量门：Ruff 通过；Import Linter 5/5 契约通过；compileall 通过。
- 契约门：V3 schema 与 OpenAPI 导出均为 current。
- 安全门：新增发布文档后 511 个候选文件密钥扫描通过；发布配置检查通过。
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

以上初始状态对应代码候选 `ed8f2dc`。执行报告提交后会形成只改文档的 PR head，必须重新核对 head 与 CI，不能复用旧结论冒充新提交通过。

## Gate 03：staging 隔离审计

- Neon：Free 计划；1 个项目；项目列表显示 Branches=1。
- 隔离结论：没有第二个 staging 分支，不能把现有唯一分支视为 staging。
- `miniprogram/.env.staging`：已跟踪，但 `TARO_APP_API_ORIGIN` 为空。
- `render.staging.yaml`：独立免费服务定义存在，`APP_ENV=staging`、`autoDeploy=false`、`WECHAT_LOGIN_ENABLED=false`，但尚无真实 hosted readiness 证据。

Gate 03 当前为 **BLOCKED**。下一项有外部副作用的动作是创建一个免费的 Neon staging 分支/数据库，并把生成的连接信息仅保存到 Render staging Secret；该动作需要在云控制台执行前确认。

## 依赖安全观察

`npm audit --omit=dev` 报告 17 个生产依赖树公告（11 moderate、3 high、3 critical）。critical 链路主要来自 Taro 4 的 H5 `swiper` 依赖；源码和微信 dist 均未引用 swiper，微信产物也不分发 `node_modules`。npm 给出的自动修复会把 Taro 4 降为 3.x，属于破坏性大版本替换，因此不在发布闭环中强制执行。该项记录为后续 Taro 官方兼容升级专项，不删除、不隐瞒。

## 当前禁止动作

- 不合并 PR #21。
- 不对生产数据库执行迁移或写入。
- 不部署或切换生产服务。
- 不创建 `v3.0.0` Tag/GitHub Release。
- 不把开发工具自动化超时写成微信真机通过。
