# 新窗口交接：游戏体验优化、仓库质量治理与 GitHub 合并

更新时间：2026-08-13（Asia/Shanghai）

仓库：`D:\my-project\girlfriend-menu-app`

远端：<https://github.com/zj1310426307-stack/girlfriend-menu-app>

## 1. 新窗口先做什么

1. 先完整阅读本文件。
2. 再阅读 `docs/PROJECT_HANDOFF.md` 和 `docs/REPOSITORY_AUDIT_2026-08-13.md`。
3. 执行 `git status -sb`、`git log -3 --oneline --decorate`，确认没有新的用户改动。
4. 不要回退、重写或重复实现本文件记录的游戏修复。
5. 如果用户继续要求发布，先区分“微信预览包”“开发版本/体验版”“正式发布”；它们不是同一件事。

## 2. 当前 Git 与发布状态

- 当前分支：`main`
- 本地 `main`：`845fa51a649a3a2e4bec1200099618128a5b0b3d`
- 远端 `origin/main`：同为 `845fa51a649a3a2e4bec1200099618128a5b0b3d`
- 提交信息：`improve game UX and repository quality`
- 功能分支：`agent/game-experience-quality`，远端仍保留，指向同一提交。
- 工作区在创建本文件前为干净状态；本文件本身是新窗口交接改动，尚未提交。
- 代码已经快进合并并成功推送到 GitHub `main`，没有额外 merge commit。
- 提交页面：<https://github.com/zj1310426307-stack/girlfriend-menu-app/commit/845fa51a649a3a2e4bec1200099618128a5b0b3d>
- 当前 GitHub combined status 只返回 `Vercel: failure`；目标地址为：
  <https://vercel.com/zj1310426307-stacks-projects/girlfriend-menu-app/GFwz3pp7pVVdqJVKzoXwSUcSnwkM>
- GitHub Actions 的 push 流程是否完成需要在新窗口重新核对；不能把本地测试通过等同于线上 CI 已通过。

## 3. 本轮用户反馈与最终修复

用户核心反馈：

- 多个游戏交互体验差。
- 斗地主横屏页面布局不合理，开局按钮无法点击。
- 中国象棋棋盘边缘棋子显示不全，之后进一步指出竖线缺失。

已经完成的修复：

### 3.1 斗地主

- 根因是 `PageMeta` 曾作为根 Grid 的第一个子项参与布局，挤占首个格子，导致主视觉与配置卡错位，开局入口被推出视口。
- 现在 `PageMeta` 位于 Fragment 中、布局容器之外。
- 横屏主视觉固定在第一列，配置/开局卡固定在第二列同一行。
- 主操作改为微信原生 `Button`，位于配置卡最前部，进入页面无需滚动即可看到。
- 增加低高度/极低高度视口压缩规则、禁用态、按压态和稳定的可访问点击目标。
- 等待情侣玩家时支持微信分享邀请。
- 游戏内操作区明确显示“轮到你 / 等待对方 / 先选牌 / 正在提交”等状态，并只在规则允许时开放“不出”。
- 已用隔离本地 SQLite、测试设备会话和微信开发者工具完成真实点击建局：`POST /api/games/landlord/create` 返回 `201`，页面进入 `.ll-room`。

### 3.2 中国象棋

- 棋盘线网宽度和上下安全边距已调整，顶部/底部棋子不再因 `overflow:hidden` 被裁成半枚。
- 旧实现用 CSS 渐变模拟竖线并用不透明河界层遮盖，真机渲染会出现竖线缺失。
- 现在绘制真实线节点：9 列、10 条横线、两条贯通边线、中间 7 列各有河界上段和下段。
- 竖线宽度提高到 `3px`，使用高对比深棕色；楚河汉界文字层保持透明。
- 九宫斜线长度和层级已修正。
- 服务端坐标、棋局规则、红黑翻转和点击映射未改变。
- 微信开发者工具验收中已实际渲染完整棋盘，脚本数到完整线网，并进行人工截图复核。

### 3.3 飞行棋、斗兽棋与通用回合体验

- 新增共享 `GameTurnGuide`，统一说明当前状态与下一步动作。
- 飞行棋骰子移到棋盘前；只有在线且轮到自己时可操作。
- 棋盘第 24 格文案与服务端 `FOOD` 事件保持一致。
- 斗兽棋和象棋允许再次点击已选棋子取消选择。
- 落子/移动请求期间立即显示目标位置反馈；断网时禁止继续提交。
- 四个游戏大厅压缩装饰区域，强化主按钮按压反馈，让关键操作更早出现在首屏。

关键文件：

- `miniprogram/src/pages/games/landlord/index.jsx`
- `miniprogram/src/pages/games/landlord/index.css`
- `miniprogram/src/components/ChessBoard.jsx`
- `miniprogram/src/components/ChessBoard.css`
- `miniprogram/src/components/GameTurnGuide.jsx`
- `miniprogram/src/components/GameTurnGuide.css`
- `miniprogram/src/pages/games/{flight,animal,chess}/`
- `miniprogram/scripts/game-pages-devtools-acceptance.cjs`
- `miniprogram/scripts/game-longevity-test.cjs`
- `miniprogram/scripts/landlord-landscape-config-test.cjs`

## 4. 微信开发者工具与预览包

用户已经明确授权过：

- 启动微信开发者工具验收。
- 将本轮优化后的当前小程序包上传到微信预览服务并生成二维码。

已完成的验收和上传：

- 斗地主真实开局专项验收通过。
- 象棋完整线网专项验收通过。
- `npm run test:game-pages:devtools` 曾通过四个游戏页面打开和人机模式切换验证。
- 最新已上传微信预览包生成时间：`2026-08-13 09:30:07`
- AppID：`wx08cb090781c3e679`
- 包体：`794903` bytes（约 776.3 KB）
- 二维码：`miniprogram/.test-tmp/preview-2.11.2-games-optimized.png`
- 预览信息：`miniprogram/.test-tmp/preview-2.11.2-games-optimized.json`

边界：

- 这是微信预览服务上传和二维码，不是上传开发版本、设置体验版或正式发布。
- 二维码目录已被 `.gitignore` 忽略，没有上传 GitHub。
- 用户仍应使用真机扫码最终复核斗地主横屏开局、中国象棋完整竖线及边缘棋子。
- 如果新窗口对代码又做了修改，旧二维码立即过期；重新上传前应再次确认用户授权针对“修改后的新包”仍然有效。不要自动沿用旧包授权。

## 5. 仓库审查与成熟开源工具集成

用户要求先审查仓库，再遵循“除非没有成熟方案，否则优先寻找并集成开源工具，减少从 0 开发，避免重复造轮子”。本轮完成：

### 5.1 Ruff

- 集成 Ruff `0.16.2`（MIT）。
- 配置位于根目录 `pyproject.toml`，当前渐进式只启用 Pyflakes `F` 类正确性规则。
- CI 后端任务增加 `python -m ruff check . ../scripts`。
- 首轮扫描发现 `crud.expire_stale_game_rooms()` 在旧数据缺少 `expires_at` 时引用未定义 TTL 常量，可能运行时报 `NameError`。
- 修复后继续从 `services.game_persistence_service` 读取统一 TTL，没有复制常量。
- 同时清理无效导入/变量，并把原先接收但未验证的骰子隐私、斗地主加入响应改为真实断言。

### 5.2 Dependabot

- 新增 `.github/dependabot.yml`。
- npm、pip 每周检查；GitHub Actions 每月检查。
- `@tarojs/*` 与 `babel-preset-taro` 分为同一更新组，避免 Taro 单包错配。
- 常规 minor/patch 更新分组，降低 PR 噪声。

### 5.3 小程序 CI 与构建缓存

- 新增 `npm run test:ci`：斗地主布局契约 + 游戏恢复/Socket 生命周期 + 客户会话契约。
- GitHub Actions 的 miniprogram 任务在生产构建后执行 `npm run test:ci`。
- 启用 Taro 官方 Webpack5 文件系统缓存：`miniprogram/config/index.js` 中 `cache.enable = true`。
- 实测首次建立缓存约 51.39 秒；第二次 Webpack 编译 1.81 秒，命令总耗时约 9.6 秒；此前冷构建约 1 分 47 秒。
- 未引入自研缓存脚本，也没有改变小程序运行时。

没有为了“使用开源库”强行替换现有游戏引擎、WebSocket 生命周期或服务端权威状态层。现有协议、持久化、隐私过滤和微信验收契约较多，通用桌游框架迁移风险高于当期收益。

详细审查记录：`docs/REPOSITORY_AUDIT_2026-08-13.md`。

## 6. 已执行验证

本轮最终验证证据：

- Ruff：通过。
- 后端：`110 passed`，11 条 SQLAlchemy/Python 3.12 SQLite datetime adapter 弃用警告。
- `npm run build:weapp`：通过。
- `npm run test:ci`：通过。
- `npm run test:landlord`：通过。
- `npm run test:games`：通过。
- 密钥扫描：`secret scan passed (367 release-candidate files)`。
- 发布配置检查：通过。
- `git diff --check`：通过；仅有 Windows LF/CRLF 提示。
- 微信开发者工具斗地主真实建局与象棋完整线网专项验收：通过。

注意：验证结果属于提交 `845fa51`。如果新窗口修改代码，必须按改动范围重跑测试，不能继续沿用这些结论。

## 7. 已知风险与建议优先级

### P0：先检查线上 CI/Vercel

- 提交 `845fa51` 的 combined status 当前显示 `Vercel: failure`。
- 先查看失败详情，判断它是否是仓库不再使用的旧网页部署、项目根目录配置错误，或真实构建问题。
- 用户若只要求诊断，先解释根因，不要擅自修改 Vercel 项目或删除集成。

### P0：真机最终复核

- 扫码检查斗地主横屏第一页是否可直接点“创建牌桌/立即开局”。
- 检查中国象棋 9 列竖线、河界断线、上下边缘棋子完整显示。
- 检查飞行棋骰子与棋盘触控、斗兽棋/象棋选择取消与落点反馈。

### P1：发布决策

- 当前 `miniprogram/package.json` 版本仍为 `2.11.1`；代码和预览备注曾使用 `2.11.2` 候选概念，但没有完成正式版本发布流程。
- 真机验收通过后再决定版本号、上传开发版本、设置体验版和正式发布。
- 正式发布前重新运行后端、构建、`test:ci`、密钥与发布配置检查。

### P1：CI 后续治理

- Ruff 当前仅启用 `F`，这是有意的渐进门禁；不要突然启用全部规则并机械格式化整个仓库。
- 可后续逐类启用导入排序和 Bugbear，但应小批量、配合测试。
- FastAPI `Depends()` 会触发部分通用 Bugbear 规则，需要框架感知配置，不应批量改写 API 签名。

### P2：历史技术债

- `backend/game_runtime/manager.py`、`backend/models.py`、`backend/schemas.py`、`miniprogram/src/api/index.js` 仍较大。
- V2.4～V2.7 老烟测脚本重复较多，后续可抽共享自动化工具，但要保留版本契约语义。
- Python 3.12 下 SQLite datetime adapter 有弃用警告，可单独规划迁移，避免混入游戏发布修复。

## 8. 安全与工作区规则

- 不提交 `backend/.env`、数据库、备份、`node_modules`、`dist`、`.test-tmp`、预览二维码、测试截图或微信私有配置。
- `miniprogram/project.private.config.json` 继续保持忽略。
- 上传微信预览、开发版本、体验版、正式版属于不同外部写操作，应分别核对授权和目标。
- 推送 GitHub 前运行密钥扫描和发布配置检查。
- 工作区出现新改动时先确认归属，不要使用 `git reset --hard`、`git checkout --` 覆盖用户工作。

## 9. 新窗口可直接复制的启动指令

```text
请先完整读取：
D:\my-project\girlfriend-menu-app\docs\THREAD_HANDOFF_2026-08-13.md

然后读取：
D:\my-project\girlfriend-menu-app\docs\PROJECT_HANDOFF.md
D:\my-project\girlfriend-menu-app\docs\REPOSITORY_AUDIT_2026-08-13.md

先执行 git status -sb 和 git log -3 --oneline --decorate，确认当前 main/工作区状态。
当前已合并并推送的基线应为 845fa51 improve game UX and repository quality。
不要重复或回退斗地主横屏开局、中国象棋完整线网、GameTurnGuide、Ruff、Dependabot、test:ci 和 Taro 构建缓存改动。

优先检查提交 845fa51 的 GitHub Actions 与 Vercel failure；如果用户要继续发布，再进行真机扫码最终验收。预览二维码位于 miniprogram/.test-tmp/preview-2.11.2-games-optimized.png，但它只代表微信预览上传，不是开发版本、体验版或正式发布。

任何新改动完成后按范围重跑 Ruff、后端测试、小程序 build/test:ci、密钥扫描、发布配置检查和 git diff --check，并如实区分本地验证、开发者工具验收、真机验收和线上发布状态。
```

## 10. 参考文档

- `docs/PROJECT_HANDOFF.md`：整体架构、API、数据模型、部署与历史阶段。
- `docs/REPOSITORY_AUDIT_2026-08-13.md`：本轮仓库审查和开源工具选择依据。
- `docs/THREAD_HANDOFF_2026-08-12.md`：上一轮完整时间线和更细的微信验收记录。
- `docs/GAME_RUNTIME_STABILITY_2_11_0.md`：长期游戏稳定性机制。
- `docs/optimization/PHASE_2C_GAME_RUNTIME_REVIEW.md`：实时边界与生产测试记录。
- `docs/CAPABILITY_MATRIX.md`：能力/验收覆盖。
