# LoveOS V3 生产发布记录

更新日期：2026-09-03

## 状态

**GATE 00-08 PASS — PRODUCTION V3 LIVE — WECHAT REVIEW NOT SUBMITTED**

## 生产发布结果

- PR [#21](https://github.com/zj1310426307-stack/girlfriend-menu-app/pull/21) 已于 2026-09-03 合并；候选 head 为 `bca5dd5be148920dd1ebe2b45047a0ac168c01d8`，标准双父合并提交为 `f363128e4db49392e64c8cc00e2e6e926957e9f9`。
- GitHub 公共 PR API 确认 `merged=true`，远端 `main` 与合并提交一致；合并提交的 `backend`、`miniprogram`、`release-safety` 与 Dependabot checks 全部通过。
- Render Free 生产服务 `srv-d92svqtaeets73akrmbg` 已部署合并提交；最终重启 deploy 为 `dep-daclp3mk1f9s73cps6gg`，服务状态为 Live。
- 生产启动守卫确认数据库已经位于当前 Alembic head `20260817_14`；最终重启日志为 `schema_changed=False`、`reference_data_seeded=False`，未重复迁移或覆盖参考数据。
- 生产 `/api/health` 返回 `ok`；`/api/ready` 返回 `ready`，PostgreSQL、database storage、authentication 与 `wechat_login` 均为 `ready`，Redis 按单实例免费架构为 `optional-disabled`。
- 生产 OpenAPI 版本为 `3.0.0`，包含 `/api/bootstrap` 与 `/api/customers/wechat-session`。
- 迁移后公开菜单仍为 19 条，与迁移前备份基线一致。V3 迁移仅新增微信身份与管理审计结构，不删除或重写客户、会话、订单、收藏、通知或游戏历史表。

## 备份与恢复证据

- 发布前只读逻辑备份 `production-api-before-v2.9-20260903T082849Z.json` 位于被 Git 忽略的本地 `backups/`：19 道菜、3 个订单、0 条评价；SHA-256 为 `4289d86bd3aee96ab4823521a6ad1ec5080fc7c93e7d0ffe7186397bfc81a184`。
- PostgreSQL 18.6 自定义格式备份 `girlfriend-menu-20260903T085441Z.dump` 为 203,551 bytes，SHA-256 为 `d1b637945731d6a7f63e4fb4fe6c408a3c7e503bd9bcbec74fe4a7f6bec19af5`。
- dump 已在仅监听本机回环地址的一次性 PostgreSQL 18.6 中恢复；19 个核心表行数与 manifest 一致，包含 24 个外键，备份 revision 为 `20260812_12`。dump、manifest、凭据与客户明细均未上传 Git。

## 小程序生产构建

- `npm run build:weapp`、`npm run test:ci` 与 `npm run test:dist` 通过。
- 产物完整性为 71 个 JavaScript 文件、140 个模块；`dist/app.json` 与 `dist/project.config.json` 均存在。
- 构建产物仅包含生产 Origin `https://girlfriend-menu-api.onrender.com`，staging Origin 命中数为 0。
- 发布配置检查与 520 个候选文件密钥扫描通过。

## 尚未执行

- 未提交微信正式审核，未发布微信正式版。
- 未创建 `v3.0.0` Tag 或 GitHub Release。
- 未开启付费实例、付费保活或超额计费。

正式审核属于独立外部发布动作，必须在上传生产构建并复核体验版后再次由发布负责人确认。
