# LoveOS V3 生产化发布包

更新日期：2026-08-28

## 当前结论

**GATE 00-02 PASS — GATE 03 BLOCKED — NO PRODUCTION CHANGE**

候选 `ed8f2dc` 的代码、迁移、契约、小程序构建、本地自动化和 PR 必需 CI 已通过。PR #21 已开放且可合并，未解决审查线程为 0。Neon 免费组织当前只有一个项目和一个分支，尚无可证明隔离的 staging 数据库，因此发布闭环停在 Gate 03；未合并、未迁移或部署生产、未创建 Tag/Release。

## 当前外部状态

- 2026-08-28 Neon 只读核验：Free 计划、1 个项目、Branches=1，独立 staging 数据库不存在。
- `miniprogram/.env.staging` 的 API Origin 仍为空，尚无 hosted readiness 结果。
- 生产状态不能用较早探针代替本轮发布证据；Gate 05 备份和 Gate 07-08 发布/冒烟均未开始。
- 在 staging hosted、微信真机和生产备份门禁完成前，不应合并 PR 或把 `3.0.0` 正式发布。

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
