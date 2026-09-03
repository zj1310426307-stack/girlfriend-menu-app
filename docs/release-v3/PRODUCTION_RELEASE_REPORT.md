# LoveOS V3 生产发布记录

更新日期：2026-09-03

## 状态

**PREPARATION IN PROGRESS — RELEASE GATES NOT SATISFIED**

## 已确认未发生

- PR #21 未合并。
- 生产数据库未执行本轮 Alembic 迁移。
- 生产 Render 服务未部署 V3、未切流；仅轮换生产管理凭据并重新部署现有 V2.11 服务。
- 已完成旧生产 API 的只读逻辑备份和校验和验证；尚未完成 PostgreSQL 级备份及隔离恢复抽查，因此 Gate 05 尚未通过。
- 未创建 `v3.0.0` Tag 或 GitHub Release。
- 微信小程序未在本轮提交审核或正式发布。

## 2026-09-03 生产只读复核

- 生产 `/api/health` 与 `/api/ready` 均返回 HTTP 200，但 OpenAPI 版本仍为 `2.11.0`。
- 生产 OpenAPI 不包含 `/api/customers/wechat-session` 和 `/api/bootstrap`，因此尚未部署本轮已在 staging 验收的 V3 微信身份与首屏聚合能力。
- PR #21 仍为 OPEN / MERGEABLE；`backend`、`miniprogram`、`release-safety` 通过，Vercel 预览失败按项目发布路径为非阻断。
- 生产管理凭据轮换后验证登录成功；凭据经一次性加密信封使用，未写入仓库、备份或日志，验收后已清空内存副本和剪贴板。
- 只读逻辑备份 `production-api-before-v2.9-20260903T082849Z.json` 已保存到被 Git 忽略的本地 `backups/`：19 道菜、3 个订单、0 条评价；SHA-256 为 `4289d86bd3aee96ab4823521a6ad1ec5080fc7c93e7d0ffe7186397bfc81a184`，与清单复算一致。
- 逻辑备份程序已修复：旧版管理员订单响应已内嵌评价，不再错误调用仅限客户会话的评价详情接口。该备份尚未替代 PostgreSQL 物理/逻辑库备份，也尚未完成隔离恢复抽查。
- 2026-09-03 新上传的小程序是指向隔离 staging Origin 的开发构建，不得直接提交正式审核。

## 进入生产前必须补齐

1. Gate 03 独立 staging 数据库与部署通过。
2. Gate 04 hosted API、核心业务、游戏/WebSocket 和微信真机通过。
3. Gate 05 生产 PostgreSQL 备份、SHA-256、行数清单与隔离恢复抽查通过。
4. PR 新 head 的审查线程为 0，必需 CI 全绿。
5. 记录生产发布前 deploy ID、数据库 revision 与回滚责任人。
