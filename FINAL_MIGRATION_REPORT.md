# LoveOS V3.0 最终迁移报告

日期：2026-08-17
执行分支：`feature/loveos-v3-refactor`
基线提交：`641c0d612d2c5b77e731e43271e0b6462fdb52b9`

## 修改内容

- 为 6 个服务端游戏增加不可变插件注册表和旧类型别名。
- 为 5 类本地游戏 AI 增加统一策略注册、难度校验、人设目录和耗时元数据。
- 把通用游戏重连迁入兼容 adapter，保留各游戏权威状态源。
- 新增认证的 `/api/bootstrap`，小程序保留旧三请求回退。
- 将小程序 HTTP transport、领域 API 和路由常量分离，旧导出/页面 URL 不变。
- 使用 Taro 原生 `subPackages` 把 15 个重游戏/管理页面移出主包。
- 复用 Pillow 生成 WebP 缩略图，保留原图和旧上传响应字段。
- 新增 JSONB 目标 migration、PostgreSQL schema 快照和 OpenAPI 3.1 快照。
- 扩充 CI：架构边界、快照漂移、迁移回滚和可重复本地性能预算。

## 删除内容

删除 0 个文件、0 个 API、0 个 WebSocket、0 张表、0 个 migration。详见 `docs/v3-migration/deleted-files-report.md`。

## 验证结果

后端 182 项测试通过；Ruff、compileall、5 条 import-linter 契约、OpenAPI/schema 快照及 Alembic 空库升降级通过。小程序生产构建、完整 CI 契约、游戏长时/重连契约和斗地主布局契约通过。微信开发者工具成功打开 V3 项目并编译飞行棋分包，编辑器显示 0 个问题；额外的 `miniprogram-automator` 页面动作在生产后端与隔离本地后端两次复测均出现模拟器 RPC timeout，因此不能标记为页面自动化通过。

主包从 803,033 bytes 降至 484,291 bytes（-39.7%）；总包为 864,114 bytes（+7.6%）。本地 bootstrap P95 22.396 ms，本地五子棋策略 AI P95 0.578 ms。

## 风险

1. 尚未在 staging PostgreSQL 执行 JSON→JSONB migration，也未采集 Render/Neon 托管延迟。
2. 尚未上传 V3 微信体验版，所以 `<2s` 启动目标与全部分包页面仍缺少真机证据。
3. Phaser 没有通过微信小程序 PoC；现有飞行棋被保留，开源 renderer 替换尚未完成。
4. 分包降低主包约 39.7%，但总包因公共块复制增长约 7.6%。
5. SQLite datetime adapter 有 11 条已知弃用警告。
6. 微信开发者工具编译通过，但页面自动化 RPC 仍需升级工具或重建自动化连接后复验。

## 回滚

本地可切换到 `backup/v2-before-refactor`。应用层新增入口均有旧接口或旧导入兼容；数据库 revision 可 downgrade 到 `20260812_12`。任何线上迁移前必须先备份并在 staging 演练。

## 后续建议

按照“先授权部署方式、再恢复 Phase 3.1-A 证据采集”的顺序推进：staging migration → 托管 API 指标 → 微信体验版真机启动/页面验收 → Phaser/Ludo 独立 PoC。没有这些证据前不应把本地结果描述为生产达标。
