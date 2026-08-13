# 仓库审查与优化记录（2026-08-13）

## 审查范围

- GitHub 远端默认分支、最近提交、开放 PR/Issue 和当前提交状态。
- 本地未提交游戏体验修复与远端 `main` 的差异。
- FastAPI 后端、Taro 小程序、自动化测试、CI 和依赖维护方式。
- 可替代自研实现的成熟开源方案及其兼容、许可证和迁移风险。

远端与本地基线均为 `4fb0dc3`（`release mini program 2.11.1`）。当前游戏体验修复仍是本地未提交工作，本轮没有覆盖或回退这些改动。

## 采用的成熟方案

### Ruff 0.16.2

Ruff 使用 MIT 许可证，统一提供 Pyflakes、pycodestyle、isort、Bugbear 等静态检查能力。本仓库先采用渐进门禁，只启用 Pyflakes `F` 规则，阻止未定义名称、无效导入和未使用变量；没有一次性格式化或重写数百处历史代码。

首轮扫描实际发现并修复了 `crud.expire_stale_game_rooms()` 在旧房间缺少 `expires_at` 时引用未定义 TTL 常量的运行时缺陷。TTL 继续由 `services.game_persistence_service` 统一拥有，未复制常量。

### GitHub Dependabot

按周检查 npm 与 pip，按月检查 GitHub Actions。Taro 全家桶归入同一更新组，避免单独升级 `@tarojs/*` 包造成版本错配；常规 minor/patch 更新也分组，减少无意义 PR 噪声。

### Taro Webpack5 持久化缓存

生产构建冷启动实测约 1 分 47 秒，且 Taro 明确提示持久化缓存未开启。现已使用 Taro 原生 `cache.enable` 配置启用 Webpack5 文件系统缓存，由框架跟踪 `config/index.js` 作为构建依赖；不增加自研缓存脚本，也不在生产包内引入运行时依赖。

## CI 优化

- 后端任务增加 `python -m ruff check . ../scripts`。
- 小程序构建后增加 `npm run test:ci`。
- `test:ci` 统一运行斗地主布局契约、游戏恢复与 Socket 生命周期、客户会话契约。
- 原有数据库迁移往返、后端全量测试、生产构建和发布安全检查保持不变。

## 未采用的替换方案

本轮没有替换游戏引擎、WebSocket 生命周期或服务端权威状态层。现有实现已经有持久恢复、版本控制、隐私过滤和微信自动化契约；将其迁移到通用桌游框架会扩大前后端协议和存量数据迁移范围，当前收益不足以覆盖兼容风险。后续如新增独立游戏，应先评估成熟引擎，再决定集成或自研。

## 验证结果

- Ruff：通过。
- 后端测试：`110 passed`。
- 小程序生产构建：通过。
- 小程序 CI 契约：全部通过。
- 未提交、未推送、未重新上传微信预览包。
