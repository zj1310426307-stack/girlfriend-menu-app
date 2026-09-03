# LoveOS V3 第三轮优化执行计划

- 计划日期：2026-08-24
- 轮次：Continuous Optimization 03
- 主题：免费 PostgreSQL 迁移门与 staging 只读验收入口
- 依据：`docs/audit/CURRENT_STATE_AUDIT.md`、`docs/audit/OPTIMIZATION_BACKLOG.md`

## 1. 目标

在不改变业务 API、数据库 schema、客户端协议且不新增付费资源的前提下：

1. 让现有 GitHub Actions 后端任务同时验证 PostgreSQL 18 的完整迁移、最后一版降级再升级和 V2 基线升级路径。
2. 提供失败关闭的 staging 只读就绪检查，拒绝空地址、HTTP、携带凭据/路径的 Origin 以及生产 API，避免误把生产环境当作 staging。
3. 校验 staging 的 health、PostgreSQL、持久图片存储、认证和微信开关状态，不输出响应正文、秘密或原始目标地址。
4. 保持 Render 登录、独立数据库创建、微信开发者工具/体验版/真机验收为有证据的外部步骤，不用本地结果替代。

## 2. 实施范围

### 工作流 A：PostgreSQL CI 迁移门

- 复用现有后端 GitHub Actions job，增加官方 PostgreSQL 18 临时 service container，不新增外部数据库账号或托管服务。
- 在隔离空库执行 `upgrade head -> downgrade -1 -> upgrade head`。
- 同一临时库降到 base 后，再执行 `upgrade 20260808_01 -> upgrade head`，覆盖当前定义的 V2 基线升级路径。
- SQLite 迁移矩阵继续保留，避免只覆盖托管方言而破坏本地兼容。

### 工作流 B：staging 只读就绪门

- 新增独立脚本，只从显式 `STAGING_API_ORIGIN` 读取目标。
- Origin 必须为纯 HTTPS origin，且不得与仓库生产 Origin 相同。
- 只请求 `/api/health` 与 `/api/ready`，禁止重定向，限制响应体积并设置超时。
- 默认允许微信登录处于 `optional-disabled`，用于先验收基础设施；传入 `--require-wechat` 后必须为 `ready`。
- 输出仅包含低敏状态与目标短摘要，不输出 URL、响应正文、邀请码、token 或配置值。

### 工作流 C：验证与交付

- 用纯单元测试覆盖 Origin 拒绝、readiness 成功/失败和微信强制模式，不连接任何外部地址。
- 用契约测试锁定 PostgreSQL service 与两条迁移路径，防止 CI 静默退回 SQLite-only。
- 运行后端全量、小程序 CI/构建、迁移、快照和发布安全门，更新当前轮次的验证、兼容、发布和 backlog 文档。

## 3. 明确不做

- 不使用生产数据库、生产秘密或生产业务数据进行 staging 验收。
- 不创建或修改 Render、Neon、微信、Redis、S3 等云端资源，不产生付费订阅。
- 不推送分支、不触发远端 Actions、不部署 staging/production；远端 CI 结果仍需候选推送后单独记录。
- 不执行会创建客户、订单、评价或游戏房间的 hosted 写入验收。
- 不把开发者工具模拟器当作微信体验版或真机证据。
- 不在本轮混入 outbox/effect ledger、lease fencing、参考数据版本迁移或业务性能重构。

## 4. 兼容策略

- 业务 HTTP/OpenAPI、WebSocket envelope、数据库 revision 和小程序 storage 均不变化。
- SQLite 仍是本地与单元测试基础；PostgreSQL service 只增加 CI 兼容门，不改变运行时连接策略。
- staging 脚本是发布辅助工具，不由后端进程或小程序运行时导入。
- 微信登录默认关闭时可先通过基础 staging 门；启用真实凭据后必须再次使用 `--require-wechat` 验收。

## 5. 回滚策略

| 改动 | 回滚方式 | 数据影响 |
| --- | --- | --- |
| PostgreSQL CI service | 回退 workflow 中 service 与迁移步骤 | 只影响 CI 覆盖；临时库随 job 销毁 |
| staging readiness 脚本 | 删除脚本和对应测试/文档 | 无运行时或业务数据影响 |
| backlog/发布材料 | 回退当前轮次文档 | 无代码、schema 或线上数据影响 |

## 6. 验收标准

- CI workflow 同时保留 SQLite 和 PostgreSQL 18 迁移链，且 PostgreSQL 覆盖 upgrade/down/up 与 from-V2。
- staging Origin 为空、非 HTTPS、含凭据/路径/查询/fragment 或复用生产 Origin 时，在网络前失败。
- health 非预期、database 非 PostgreSQL、storage/authentication 非 ready 时失败。
- 默认模式接受微信 `optional-disabled|ready`；`--require-wechat` 只接受 `ready`。
- 定向与全量自动化通过，OpenAPI/schema 快照无变化，仓库秘密扫描与发布配置门通过。

## 7. 发布门

本轮本地完成不等于 staging 已部署。候选提交推送并取得 PostgreSQL Actions 绿灯后，仍需由已登录的 Render 会话创建独立免费 staging、配置独立空数据库和秘密，再运行只读门。随后初始化微信开发者工具、生成 staging 构建并完成体验版/真机验收；生产继续保持手工发布。

## 8. 执行结果

本轮本地实施已于 2026-08-24 完成。现有 backend job 已加入 PostgreSQL 18 临时 service 和两条迁移矩阵；staging 只读门已实现目标隔离、禁重定向、响应限额、持久存储/认证检查和微信两阶段判定。20 项定向测试、272 项后端全量测试、小程序 CI/生产构建、SQLite 迁移矩阵、快照、架构、发布配置、密钥与真实本地启动门均通过。

工作区没有 Docker/PostgreSQL 服务，候选也未推送，所以 PostgreSQL service 仍是“配置与合同通过、远端执行待验收”。Render 页面未登录，微信开发者工具用户配置未初始化，因此未创建云资源、未运行 hosted readiness、未生成体验版/真机证据，也未触碰 production。
