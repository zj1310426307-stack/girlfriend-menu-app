# LoveOS V3 Staging 验收记录

更新日期：2026-09-03

## 状态

**IN PROGRESS — HOSTED + REAL WECHAT DEVTOOLS PASS / WECHAT REAL DEVICE PENDING**

## 隔离前置审计

| 检查 | 状态 | 证据 |
| --- | --- | --- |
| 免费计划 | PASS | Neon 与 Render 控制台均显示 Free；Render 明示空闲休眠 |
| 独立 staging 数据库/分支 | PASS | 新建 Neon 项目 `loveos-staging-release-00`，AWS 新加坡、PostgreSQL 18；创建时存储为 0，不含生产业务数据 |
| 独立 staging API Origin | PASS | `https://girlfriend-menu-api-staging.onrender.com`，与生产 Origin 不同 |
| staging 服务 | PASS | Render 服务 `girlfriend-menu-api-staging` 首次部署成功，来源 `d11a708`，健康检查持续 200 |
| CloudBase 免费备用环境 | BLOCKED | 已尝试创建 `loveos-staging`（`loveos-staging-d4gchuaw70bdc5234`）；0 元、6 个月、3000 资源点，且页面明确不支持加购资源包和开启按量付费；费用中心显示“发货失败已退款”，1 个资源发货失败、实付 0 元，尚未部署云托管 |
| 生产库复用防线 | PASS | 只读门拒绝 production Origin；hosted readiness 确认数据库为 PostgreSQL，未使用生产 API Origin |

## 待执行验收

- [x] 创建免费、独立、无生产业务数据的 Neon staging 项目/数据库。
- [x] 仅在 Render staging Secret 配置独立 `DATABASE_URL` 与 staging 认证 Secret。
- [x] 部署 PR #21 的冻结候选 `d11a708`；启动快路径完成迁移/参考数据检查。
- [x] `/api/health` 返回 200 且标识 LoveOS API。
- [x] `/api/ready` 返回 `status=ready`、`database=postgresql`、持久化存储 ready、认证 ready。
- [x] 在微信关闭状态通过只读门；`wechat_login=optional-disabled` 符合第一阶段策略。
- [x] 使用 staging 专用邀请码完成客户会话、bootstrap、存量设备认领/换机恢复与旧会话撤销。
- [x] 完成菜单/收藏、管理登录与管理 WebSocket、数据库图片上传/下载、订单归属隔离、重复点单预览、状态流转、评价、撤回，以及双客户游戏 WebSocket/重连验收。
- [x] 验收凭据在一次诊断输出风险后立即二次轮换；新管理员首次登录已完成数据库 verifier 轮换，复验通过，明文未写入仓库、文件或验收输出。
- [x] 配置真实微信凭据并用 `--require-wechat` 复核。
- [ ] 使用真实微信 code 完成新用户邀请、存量 OpenID 原地绑定与新手机恢复同一业务身份。
- [x] staging 小程序构建完成，`dist/app.json` 存在，产物完整性检查通过且 API Origin 指向独立 Render staging。
- [x] 微信开发者工具使用本轮 staging 产物普通启动，红色应用错误为 0；MCP 自动化只签署页面结构与本地交互，不替代真实微信登录和真机业务验收。
- [ ] 微信真机覆盖冷启动、弱网、断网重连及核心业务。

## 证据边界

2026-08-28 的 hosted 只读门返回：`database=postgresql`、`storage=ready`、`authentication=ready`、`redis=optional-disabled`、`wechat_login=optional-disabled`。无凭据访问 `/api/bootstrap` 返回 401，符合设备邀请码/会话边界。随后使用 staging 环境构建微信小程序，`dist/app.json` 与 71 个 JavaScript 产物生成成功，140 个模块通过完整性检查，编译产物包含独立 staging API Origin。

同日两次 hosted 写链路验收均通过，第二次在凭据再次轮换后通过安全加密交接执行。8 个检查域依次覆盖 health/readiness、客户会话/bootstrap、存量恢复与旧会话撤销、菜单收藏、管理认证/WebSocket、持久图片、订单/评价/撤回，以及双客户端游戏 WebSocket/重连；最终结果为 PASS。验收输出只保留阶段、状态、耗时和候选短摘要，不保留凭据、令牌或业务对象标识。

2026-08-29 已定位 Windows 微信开发者工具把 IDE HTTP 服务与自动化 WebSocket 绑定到同一端口、不同回环地址的问题；改用未被 HTTP 服务抢占的回环地址后，系统信息读取与模拟器清缓存均通过。随后使用安全注入的 staging 邀请码重跑，开发者工具稳定返回 `MINIPROGRAM_DOMAIN_NOT_ALLOWED`，请求未到达 Render。当前应用交互不能签署通过：需先在 AppID `wx08cb090781c3e679` 的微信公众平台配置中确认 staging HTTPS Origin 位于 `request` 合法域名，并同步核对 socket、uploadFile 与 downloadFile 域名，再重新编译/清缓存验收。真实微信 code2Session、OpenID 绑定和微信真机门禁继续保持未通过状态。

2026-08-30 的公众平台截图确认 request、socket、uploadFile、downloadFile 列表均包含 Render staging 主机，运行时 `getAccountInfoSync` 也确认 AppID 为 `wx08cb090781c3e679`、环境为 develop。清除开发者工具全部缓存并重新获取 AppID 权限后，严格校验仍稳定返回同一域名拒绝，因此已排除未保存、错误运行时 AppID和普通本地缓存。当前推断为 Render 共享域名不满足微信严格域名合规要求；在得到权威平台状态前不把推断写成定论。

2026-09-02 已尝试创建 CloudBase 免费体验环境 `loveos-staging`（环境 ID：`loveos-staging-d4gchuaw70bdc5234`）。购买页确认费用为 0 元、试用期 6 个月、3000 资源点，并明确不支持加购资源包和开启按量付费。环境持续显示 `UNAVAILABLE`；费用中心对应云开发体验版订单显示“发货失败已退款”，1 个资源发货失败，折后总价与实付金额均为 0 元。控制台对 `tcb/DescribeUserEnvRes` 的调用同时返回 `InvalidParameter`，原因为 `env status invalid`。这些证据将状态从“等待初始化”收敛为“腾讯云发货失败，等待供应商支持”，不得直接删除重建或改用付费套餐。账号标识和完整请求 ID 不写入仓库；尚未部署云托管、切换小程序 Origin 或产生新的 hosted/真机通过证据，Gate 04 状态不变。

2026-09-02 当前 PR #21 候选的小程序全量合同测试、staging 构建和产物完整性检查通过；微信开发者工具上传 `3.0.0` 成功，总包 849.9 KB、主包 444.4 KB。微信公众平台版本管理页显示最新提交时间为 2026-09-02 15:31:54，版本带“体验版”标记，操作菜单为“取消体验”，因此当前上传构建已成为体验版。Render staging 的严格域名拒绝、真实微信登录、OpenID 绑定及真机业务流程仍未通过，Gate 04 保持进行中；未提交审核、未正式发布。

同日通过 MCP 直接连接微信开发者工具自动化 WebSocket `127.0.0.1:9330` 完成页面级验收。运行时确认 AppID 与候选项目一致、环境为 `develop`、基础库为 3.15.2。冷启动邀请码页、菜单、点菜单、一起玩、情侣中心、个人资料、消息、购物车、情侣积分/记录/成就/游戏记录/任务/时间轴、排行榜、陪伴小结、双人大话骰大厅均成功打开；一起玩大厅渲染 6 个游戏卡片并可点击进入五子棋。五子棋、飞行棋、斗地主、斗兽棋和中国象棋大厅均完成双人/人机模式切换检查，今晚转盘完成新增选项交互，单机 3D 骰子完成 WebGL 画布和场景初始化。验收期间应用运行时异常为 0、错误级控制台为 0；隔离假会话产生 8 条 `MINIPROGRAM_NETWORK_TIMEOUT` 信息级标记，不作为 hosted 业务通过证据。模拟器原存储已完整恢复。真实邀请码提交、微信 code2Session、OpenID 绑定和真机网络/业务流程仍未完成，因此不重新上传、不提交审核，Gate 04 结论不变。

后续重新生成同一 `3.0.0` staging 候选并复验：小程序合同测试、Webpack 构建、71 个 JavaScript / 140 个模块产物完整性、发布配置与 518 个候选文件密钥扫描均通过。新构建在微信运行时内直接请求 staging `/api/health` 返回 HTTP 200，证明当前 AppID 的 request 合法域名与 HTTPS 网络链路已生效，2026-08-29 的严格域名阻塞项由此关闭；冷启动、6 游戏入口和单机 3D 场景复验仍为 0 运行时异常、0 错误级控制台。严格 hosted 门 `check_staging_readiness.py --require-wechat` 仍失败于 `wechat_login=optional-disabled`，源码语义明确对应 `WECHAT_LOGIN_ENABLED=false`。在服务端配置真实 `WECHAT_APP_ID`、`WECHAT_APP_SECRET` 并启用微信登录前，不上传新的体验构建。

2026-09-03 在 Render staging 配置真实微信凭据并重新部署后，严格 hosted 门 `check_staging_readiness.py --require-wechat` 通过，返回 PostgreSQL、database storage、authentication 与 `wechat_login=ready`。微信开发者工具通过真实 `wx.login` 一次性 code 完成首次邀请码绑定，随后清除本地客户会话并再次获取新 code；第二次请求未携带邀请码仍返回同一客户身份，两轮 `/api/bootstrap` 均为 HTTP 200。恢复后的会话已持久化，首页冷启动直接进入已认证界面，应用运行时异常、连接错误与错误级控制台均为 0。邀请码、code、OpenID、客户标识和 token 均未写入仓库或验收输出。

同日复核上传候选：`test:dist` 通过 71 个 JavaScript 文件 / 140 个模块，目录共 182 个文件、891,235 bytes，`dist/app.js` SHA-256 为 `2AADD07F0912A74F2038C385974D3B597A86B80DC010F5F477EDA015AD76E45E`。微信开发者工具再次上传 `3.0.0` 成功，总包 849.9 KB、主包 444.4 KB。2026-09-03 公众平台版本管理页随后权威显示该最新开发版本提交时间为 15:34:34、项目备注为 `LoveOS V3 staging real WeChat login acceptance`，并带“体验版”标记；体验二维码路径为 `pages/index/index`。该证据仅关闭最新上传快照的体验版状态，不代表提交审核或正式发布。真实微信开发者工具链路不能替代真机弱网、切后台、断线恢复、存量账号原地绑定或双设备在线对局，Gate 04 因此仍为进行中。
