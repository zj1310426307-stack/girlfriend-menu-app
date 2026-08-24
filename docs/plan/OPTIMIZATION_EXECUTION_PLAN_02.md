# LoveOS V3 第二轮优化执行计划

- 计划日期：2026-08-24
- 轮次：Continuous Optimization 02
- 主题：认证就绪可信化与运行日志隐私保护
- 依据：`docs/audit/CURRENT_STATE_AUDIT.md`、`docs/audit/OPTIMIZATION_BACKLOG.md`

## 1. 目标

在不改变业务 API、数据库 schema、客户端协议且不引入付费资源的前提下：

1. 让 `/api/ready` 同时检查客户登录、管理员登录和令牌签发的最低配置，避免服务无法登录却显示 ready。
2. 让 HTTP、Redis、游戏状态、维护任务和 WebSocket 日志不再记录动态 URL、缓存键和房间码原文。
3. 保留足够的低基数诊断信息，并通过自动化 sentinel 测试证明敏感原文不会进入日志。
4. 形成兼容、验证、回滚和发布材料，保持本地候选与外部验收边界清晰。

## 2. 实施范围

### 工作流 A：认证 readiness

- 新增 service 层认证就绪检查，API 路由只负责聚合和响应塑形。
- 检查客户邀请码、管理员邀请码、管理员登录凭据和管理员 token secret。
- 已存在且启用的管理员账户以数据库密码哈希为权威；只有尚无账户时才要求 bootstrap 密码或哈希。
- 已存在但禁用的管理员账户视为 release-blocked，避免配置值绕过账户状态。
- 在 staging/production 中拒绝管理员与客户共用同一邀请码；test/development 保持兼容。
- readiness 只返回状态和缺失项名称，不返回任何秘密或哈希。

### 工作流 B：日志隐私

- HTTP 访问日志使用框架匹配后的路由模板；未匹配请求固定记为 `/unmatched`。
- 对缓存键和房间码生成进程内稳定、跨重启不可关联的 HMAC 短引用。
- 隐私敏感异常只记录异常类型，不记录可能携带输入原文的异常消息和堆栈。
- 为 HTTP、cache 和引用生成器增加 sentinel 测试，并覆盖主要游戏日志调用点。

### 工作流 C：验证与交付

- 运行定向测试后执行全量后端、小程序、构建、迁移、启动和发布安全门。
- 检查 OpenAPI/schema 快照不变，证明公开业务契约未修改。
- 更新当前架构说明、兼容/迁移说明、验证报告和第二轮发布说明。

## 3. 明确不做

- 不部署 production 或 staging，不连接外部 PostgreSQL、Redis、微信或对象存储。
- 不创建付费资源，不改变现有 free Blueprint 规格。
- 不新增或修改业务 HTTP 路由、DTO、WebSocket envelope、token 格式或数据库 revision。
- 不在本轮实现 outbox/effect ledger、lease fencing、全局 scheduler ownership 或集中日志平台。
- 不把本地测试结果描述为微信真机、隔离 staging 或生产验收完成。

## 4. 兼容策略

- `/api/ready` 未进入 OpenAPI；保留 HTTP 200 和原有字段，仅新增 `authentication` 字段并扩展顶层状态聚合条件。
- development/test 中允许管理员与客户邀请码相同，避免破坏现有本地流程；托管环境要求分离。
- 日志字段由原始值改为 `*_ref`，属于运维安全收紧，不改变业务行为、数据或客户端响应。
- HMAC 盐只存在于单个进程内；引用用于同一实例内短期排障，不作为业务 ID 或跨实例关联标识。

## 5. 回滚策略

| 改动 | 回滚方式 | 数据影响 |
| --- | --- | --- |
| authentication readiness | 回退 readiness service 与聚合字段 | 无 schema/data 迁移；只影响发布判定 |
| HTTP 路由模板日志 | 回退中间件日志字段 | 无业务数据影响；不建议恢复动态路径原文 |
| room/cache 短引用 | 回退对应日志调用 | 无业务数据影响；不建议恢复敏感原文 |
| 异常类型日志 | 回退日志级别/字段 | 无业务数据影响；需继续避免异常消息泄密 |

## 6. 验收标准

- 缺客户邀请码、管理员邀请码、管理员凭据或有效 token secret 时 authentication 为 `release-blocked`。
- 已有启用管理员账户时不要求 bootstrap password；禁用账户时不能显示 ready。
- 托管环境中客户/管理员邀请码相同会阻止 release；test/development 保持现有兼容。
- readiness 响应和日志均不包含配置秘密、密码哈希、动态路径 sentinel、缓存键或房间码原文。
- 已匹配动态请求记录路由模板；未知动态请求记录 `/unmatched`。
- 全量 pytest、Ruff、Import Linter、compileall、schema/OpenAPI、小程序 CI/构建、迁移和启动 smoke 通过。

## 7. 发布门

本轮完成本地代码与验证不代表允许生产发布。生产前仍需在隔离免费 staging 配置独立秘密，确认 `/api/ready` 的 authentication/storage/wechat 三项，并完成微信 DevTools、体验版和真机核心流程。生产继续手工发布，发布前完成可恢复备份。

## 8. 执行结果

待本轮实现和验证完成后补充；在此之前状态为“实施中”。
