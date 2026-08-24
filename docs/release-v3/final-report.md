# LoveOS V3 生产化实施最终报告

## 结论

**本地发布候选通过；外部发布待授权。**

本轮以兼容式方式完成微信标准身份、后台账号散列/审计和首屏收敛，没有删除旧 API、旧 Customer、旧订单、旧游戏数据或原有设备恢复桥梁。

## 关键安全不变量

- AppSecret 只在后端 `SecretStr` 和 code2Session adapter 中使用。
- `session_key` 在适配器边界即丢弃，数据库 schema 无此字段。
- openid 已绑定其他用户、当前用户已绑定其他 openid 时返回 409，不静默合并身份。
- 客户 token 继续只保存 SHA-256 hash；多设备 session 独立且可撤销。
- 管理密码只保存 scrypt verifier；审计表无法保存提交的凭据。
- `/api/ready` 在微信开关已启用但凭据不全时明确 release-blocked。

## 兼容性

- 原 89 条 HTTP 业务基线全部保留，新增微信 session 后当前为 90 条 `/api/*` operation。
- 3 条 WebSocket 路由未改。
- 管理登录请求/响应字段未改。
- 首页旧五端点保留，小程序在 bootstrap 不可用时自动降级。
- Alembic 只新增表，未重写已有数据。

## 明确不做

- 不重复引入 Nginx、另一套 session 表、另一套 cache、另一套 telemetry 或前端请求层。
- 不在缺少配对/解绑业务定义时虚构 `couple_bindings` 状态机。
- 不把多 worker 当作免费性能优化；当前 WebSocket/定时任务所有权不支持盲目扩进程。
- 不自动操作 GitHub、Render、生产数据库或微信公众平台。

## Git 与外部状态

- 本地分支：`feature/wechat-production-v3`。
- 起点：`aedae15`。
- 本轮尚未 commit、push 或创建/合并 PR。
- 微信小程序 `3.0.0` 已上传为开发版本，但尚无体验版成功证据。
- 2026-08-20 生产 API 仍为 `2.11.0`，缺少 V3 微信 session 与 bootstrap 接口；V3 后端尚未证明已部署。

## 下一授权门

1. 审阅并提交本地 RC。
2. 部署隔离 staging，配置真实微信凭据并收集 hosted/真机证据。
3. 通过 [微信发布清单](wechat-release-checklist.md)。
4. 再单独授权生产部署、微信体验版上传或正式发布。
