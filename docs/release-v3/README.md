# LoveOS V3 生产化发布包

更新日期：2026-08-23

## 当前结论

**LOCAL RELEASE CANDIDATE PASS — DEVELOPMENT BUILD UPLOADED — BACKEND ROLLOUT PENDING**

代码、迁移、契约、小程序构建和本地自动化门禁已经通过。微信小程序 `3.0.0` 已上传为开发版本，但没有证据证明已设为体验版；当前仍未执行本轮 Git commit/push、Render V3 部署、生产数据库迁移、提交审核或正式发布。

## 当前外部状态

- 2026-08-20 只读核验：生产 `/api/health` 返回 200，服务存活。
- 生产 OpenAPI 仍为 `2.11.0`，尚无 `POST /api/customers/wechat-session` 和 `GET /api/bootstrap`。
- 生产 `/api/ready` 返回 200，但仍是旧结构，没有 V3 微信登录就绪项；不能据此宣称 V3 后端已就绪。
- 在后端 V3 部署和 staging 验收完成前，不应把 `3.0.0` 设为体验版。

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
