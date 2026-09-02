# LOVEOS-RELEASE-00 执行报告

更新日期：2026-09-02

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

2026-08-30 已取得公众平台四类服务器域名列表截图，并核对开发者工具运行时 AppID 一致；全量缓存刷新后仍被严格校验拒绝。为保留 0 元约束并避免重写业务 API，新增 CloudBase 容器构建入口和免费 staging 指南，计划继续复用 Neon staging。

2026-09-02 已尝试创建 CloudBase 免费体验环境 `loveos-staging`（环境 ID：`loveos-staging-d4gchuaw70bdc5234`）。购买页确认费用为 0 元、试用期 6 个月、3000 资源点，并明确免费体验版不支持加购资源包或开启按量付费。环境持续显示 `UNAVAILABLE`；费用中心对应云开发体验版订单显示“发货失败已退款”，1 个资源发货失败，折后总价与实付金额均为 0 元。控制台调用 `tcb/DescribeUserEnvRes` 返回 `InvalidParameter`，原因为 `env status invalid`，与发货失败状态一致；账号标识和完整请求 ID 未写入仓库。本次创建未成功完成，下一步需由腾讯云支持确认发货失败原因及免费体验资格恢复方式；尚未部署云托管、切换小程序 Origin 或产生运行证据，Gate 04 结论不变。

同日已重新验证并上传当前 PR #21 的小程序 `3.0.0` staging 构建：全量合同测试、生产模式 staging 构建和产物完整性检查通过，上传结果为总包 849.9 KB、主包 444.4 KB。微信公众平台版本管理页显示提交时间 2026-09-02 15:31:54，版本带“体验版”标记，操作菜单显示“取消体验”，确认当前上传构建已经是体验版。该外部状态仅关闭“体验版状态证据”缺口；严格域名、真实微信登录、OpenID 绑定及真机验收仍未完成，Gate 04 保持进行中，未提交审核或正式发布。

随后通过 MCP 连接微信开发者工具自动化端口完成候选页面级验收：冷启动邀请码页、5 个主导航域及主要资料/消息/情侣记录页面均可打开；一起玩大厅显示 6 个游戏入口并完成点击路由；五子棋、飞行棋、斗地主、斗兽棋、中国象棋均通过大厅结构与人机模式切换；转盘新增选项通过；单机 3D 骰子 WebGL 场景完成初始化；双人大话骰大厅可加载。应用运行时异常与错误级控制台均为 0，隔离假会话的网络请求仅产生 8 条信息级超时标记，验收结束后模拟器存储已原样恢复。本证据只关闭开发者工具页面结构/本地交互子门，不包含真实微信凭据、code2Session、OpenID 绑定、在线对局或真机证据；因此不重新上传体验版，Gate 04 仍为进行中。

在重建同一 `3.0.0` staging 产物后，合同测试、构建、产物完整性、发布配置和密钥扫描再次通过；微信运行时直接访问 staging `/api/health` 返回 200，确认 request 合法域名已生效，旧的严格域名阻塞项关闭。严格 hosted readiness 仍因 `wechat_login=optional-disabled` 失败，对应 Render 当前仍设置 `WECHAT_LOGIN_ENABLED=false`。因此本轮停止在上传之前：已有 `3.0.0` 体验版保持不变，待服务端真实微信凭据启用并完成 code2Session/OpenID 验收后再上传新的候选。

## 依赖安全观察

`npm audit --omit=dev` 报告 17 个生产依赖树公告（11 moderate、3 high、3 critical）。critical 链路主要来自 Taro 4 的 H5 `swiper` 依赖；源码和微信 dist 均未引用 swiper，微信产物也不分发 `node_modules`。npm 给出的自动修复会把 Taro 4 降为 3.x，属于破坏性大版本替换，因此不在发布闭环中强制执行。该项记录为后续 Taro 官方兼容升级专项，不删除、不隐瞒。

## 当前禁止动作

- 不合并 PR #21。
- 不对生产数据库执行迁移或写入。
- 不部署或切换生产服务。
- 不创建 `v3.0.0` Tag/GitHub Release。
- 不把开发工具自动化超时写成微信真机通过。
