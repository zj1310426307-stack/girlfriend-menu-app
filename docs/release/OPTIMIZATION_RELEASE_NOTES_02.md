# Continuous Optimization 02 发布说明

- 候选日期：2026-08-24
- 候选分支：`feature/continuous-optimization-02`
- 状态：本地候选完成，未部署 staging/production，未发布微信体验版

## 本轮亮点

### 更可信的发布就绪状态

`/api/ready` 新增 `authentication`，会检查客户/管理员邀请码、管理 token secret、管理员账号状态和 password verifier。服务仍能存活但登录链路不可用时，总状态会明确显示 `release-blocked`，且响应只包含安全配置项名称。

staging/production 现在要求客户与管理员邀请码分离。已有启用管理员继续以数据库 verifier 为权威；损坏或非项目标准格式的环境/数据库 hash 会在发布前暴露。

### 日志默认保护房间与用户标识

HTTP 日志从动态 path 改为 route template；未知路径固定为 `/unmatched`。请求 ID、Redis key 和房间码使用不可离线枚举的进程内 HMAC 短引用。相关故障不再输出可能夹带输入的异常消息或 traceback，只记录异常类型。

标准免费启动入口关闭 Uvicorn 原始 URL access log，避免框架在应用脱敏日志之外重复泄露动态路径。业务状态码、耗时和同进程关联能力仍然保留。

## 兼容性

- 业务 HTTP、WebSocket、token、DTO、小程序页面和本地存储不变。
- 数据库 head 仍为 `20260817_14`，没有新 migration。
- OpenAPI 与 schema 快照无变化。
- `/api/ready` 保持 HTTP 200 和原字段，只新增 authentication 并扩展总状态判定。
- 运维日志字段有意从 `id/path/key/room` 迁移到 `request_ref/route/key_ref/room_ref`。

## 运维动作

发布到隔离 staging 前：

1. 使用项目脚本生成 `ADMIN_PASSWORD_HASH`，配置长度足够的 `ADMIN_SECRET`。
2. 保证 `ADMIN_INVITE_CODE` 与 `CUSTOMER_INVITE_CODE` 不同。
3. 检查 `/api/ready.authentication.status=ready` 且 `missing=[]`。
4. 更新依赖旧日志字段的查询或告警。
5. 确认托管日志中没有 Uvicorn 原始 URL 行，应用 route template 日志正常采集。

## 验证摘要

- 后端：252 passed；Ruff、compileall、5 条 Import Linter 合同通过。
- 合同：OpenAPI/schema current。
- 小程序：完整 CI 与 WeApp 生产构建通过；主包 469,038 B，总产物 888,826 B。
- 数据库：empty/down/up/from-V2 SQLite migration matrix 通过。
- 运行：真实 `serve.py` health/ready/dynamic-route smoke 通过。
- 发布门：免费配置检查通过；497 个候选文件密钥扫描通过。

## 尚未发布与已知限制

本说明是本地 release candidate 记录，不代表线上发布。隔离 PostgreSQL staging、Render 日志、微信 DevTools/体验版/真机、双设备游戏、生产备份恢复均待完成。跨实例订单附属动作严格不丢不重仍需要后续 outbox/effect ledger；本轮没有扩大该承诺。
