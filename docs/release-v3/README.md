# LoveOS V3 生产化发布包

更新日期：2026-09-03

## 当前结论

**GATE 00-08 PASS — PRODUCTION V3 LIVE — WECHAT REVIEW NOT SUBMITTED**

候选 head `bca5dd5` 的代码、迁移、契约、小程序构建、staging hosted 验收、真实微信 OpenID 恢复链路与发布负责人真机验收均已通过。PR #21 已通过合并提交 `f363128` 进入 `main`，Render Free 生产服务已完成 V3 数据库准备与部署；生产 OpenAPI 为 `3.0.0`，health/readiness、authentication 与微信登录均为 ready。尚未提交微信正式审核，也未创建 Tag/Release。

## 当前外部状态

- 2026-08-28 Neon：独立 Free staging 项目 `loveos-staging-release-00`，AWS 新加坡、PostgreSQL 18，创建时存储为 0。
- Render：隔离 staging 与生产服务均保持 Free；生产最终 deploy `dep-daclp3mk1f9s73cps6gg` 已上线合并提交 `f363128`。
- Hosted 业务验收：客户会话/恢复、菜单收藏、管理认证、图片、订单/评价/撤回、管理与游戏 WebSocket/重连共 8 个检查域通过；凭据二次轮换后的安全复验同样通过。
- `miniprogram/.env.staging` 指向独立 staging Origin；生产 Origin 和数据库未复用。
- Gate 05 的 PostgreSQL dump、SHA-256、表行数、24 个外键与隔离恢复已通过；dump 和客户明细未上传 Git。
- 生产 `/api/ready` 全部关键组件 ready，OpenAPI V3 两个关键入口已上线；微信正式审核仍需独立确认。

## 本轮完成

- 标准微信登录：`wx.login -> code2Session -> openid -> Customer -> CustomerSession`。
- 存量设备账号原地绑定微信，换机继续使用同一个 `customer_id`，订单、积分和游戏记录不拆分。
- 只保存 `openid` / 可选 `unionid`，不保存 `session_key`，AppSecret 只存在后端配置。
- 数据库管理账号、scrypt 密码散列、最小化登录审计和配置驱动的受控密码轮换。
- `/api/bootstrap` 聚合推荐、今日任务、最近订单和恋爱值；旧端点全部保留。
- 首页收敛到首屏核心信息，五个一级入口继续由 tabBar 承担。
- OpenAPI、PostgreSQL schema、Alembic、Render 变量、发布检查和回归测试同步。

## 未重复建设

现有 FastAPI/Taro、菜单本地缓存、WebP 多尺寸、分包、Redis 可选适配、请求限流、输入校验、请求日志、OpenTelemetry、数据库连接池和 `/api/health` / `/api/ready` 均直接复用。

## 文档索引

- [架构与取舍](architecture.md)
- [部署与回滚](deployment.md)
- [免费托管启动计划](performance-rollout-plan.md)
- [监控与告警](monitoring.md)
- [微信发布清单](wechat-release-checklist.md)
- [测试报告](test-report.md)
- [最终实施报告](final-report.md)
- [RELEASE-00 执行报告](RELEASE_00_EXECUTION_REPORT.md)
- [Staging 验收](STAGING_ACCEPTANCE.md)
- [生产发布记录](PRODUCTION_RELEASE_REPORT.md)
- [回滚方案](ROLLBACK_PLAN.md)
- [证据清单](RELEASE_EVIDENCE_MANIFEST.json)
