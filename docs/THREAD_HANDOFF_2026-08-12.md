# 当前 Codex 窗口交接摘要（2026-08-12）

> 用途：在新的 Codex 窗口中继续维护 `girlfriend-menu-app`。本文区分“已经提交/上传的状态”和“当前工作区尚未提交的改动”，不得把计划或本地预览误认为已发布。

## 1. 新窗口先读这里

### 工作区与远程仓库

- 本地项目：`D:\my-project\girlfriend-menu-app`
- GitHub：`https://github.com/zj1310426307-stack/girlfriend-menu-app`
- 分支：`main`
- 已提交基线：`4fb0dc3 release mini program 2.11.1`
- 当前 `main` 与 `origin/main` 对齐，但工作区有一批 **未提交的四游戏体验修复**。
- 不要执行 `git reset --hard`、`git checkout -- .` 或覆盖式重新生成；先检查 `git status` 和 `git diff`。

### 当前产品与部署

- 产品定位：情侣私厨协作工具，同时包含“我们”和“一起玩”互动模块。
- 小程序：Taro 4 + React 18。
- 后端：FastAPI + SQLAlchemy 2 + Alembic。
- 生产数据库：Neon PostgreSQL；本地允许 SQLite 回退。
- Render API：`https://girlfriend-menu-api.onrender.com`
- 微信小程序 AppID：`wx08cb090781c3e679`
- 当前源码/体验版基线：`2.11.1`（以仓库交接文档和提交记录为准）。
- 下一候选版本：`2.11.2`，尚未修改版本号、提交、推送或上传体验版。
- 微信开发者工具 CLI：`F:\浏览器\微信web开发者工具\cli.bat`

### 当前必须继续完成的任务

用户最后的明确发布门槛是：

> 在微信开发者工具和真机确认飞行棋、斗地主、中国象棋、斗兽棋四个页面后，再上传体验版。

因此下一窗口应按此顺序继续：

1. 保留并审查当前未提交改动。
2. 修复或清理无效的开发者工具自动化脚本。
3. 在开发者工具中实际打开四个页面并检查交互。
4. 使用已经生成的预览二维码进行真机验收。
5. 只有四页均验收通过后，才把小程序版本升为 `2.11.2`。
6. 再执行完整测试、提交、推送 GitHub、上传微信开发版本，并在公众平台设为体验版。

不要在缺少真机结论时声称已经验收或上传。

## 2. 当前未提交工作区（非常重要）

2026-08-12 最后一次检查时，以下文件有未提交修改：

```text
backend/tests/test_chess_engine.py
miniprogram/scripts/game-longevity-test.cjs
miniprogram/scripts/landlord-landscape-config-test.cjs
miniprogram/scripts/v24-smoke-test.cjs
miniprogram/scripts/v25-smoke-test.cjs
miniprogram/scripts/v26-smoke-test.cjs
miniprogram/src/components/AnimalBoard.css
miniprogram/src/components/AnimalBoard.jsx
miniprogram/src/components/ChessBoard.css
miniprogram/src/components/ChessBoard.jsx
miniprogram/src/components/DiceButton.css
miniprogram/src/components/DiceButton.jsx
miniprogram/src/components/FlightBoard.css
miniprogram/src/components/FlightBoard.jsx
miniprogram/src/pages/games/animal/index.css
miniprogram/src/pages/games/animal/index.jsx
miniprogram/src/pages/games/landlord/index.css
miniprogram/src/pages/games/landlord/index.jsx
```

另有未跟踪文件：

```text
miniprogram/scripts/game-pages-direct-acceptance.cjs
```

这个 direct-acceptance 脚本是为绕过微信开发者工具自动化卡死而临时创建的，但同样会挂起。继续前应审查；如果确定无用，用 `apply_patch` 删除，不要随意留下失败脚本。

当前 diff 规模约为 18 个已跟踪文件，`201 insertions / 125 deletions`。

## 3. 四个游戏的本地修复内容

### 飞行棋

- `DiceButton` 在等待服务端结果时每 70ms 切换点数，动画约 0.24 秒，提供立即反馈。
- `FlightBoard` 视觉从单调方形路线调整为 28 节点环形路线，并标记互动事件格。
- 只调整客户端表现，没有修改生产后端规则、捷径或结算协议。
- 曾尝试后端捷径规则，后来已经撤销，避免本地小程序与线上后端不兼容。

待真机确认：

- 点击掷骰后是否立即有动效。
- 服务端结果回来后是否正确落位。
- 路线是否清楚、事件格是否可读、小屏是否拥挤。

### 斗地主

- 大厅增加标题与更清楚的启动入口。
- 开始按钮增加语义标签、可点击层级和更大触控区域。
- 增加极矮横屏（`max-height: 280px`）紧凑布局，避免开始按钮被挤出屏幕。

待真机确认：

- 进入后是否正确切到横屏。
- 在短屏 iPhone 上是否能看到并点击“开始游戏”。
- 手牌区、中央出牌区和操作栏是否互不遮挡。

### 中国象棋

- 棋盘从“格子内摆棋”改为标准 9×10 交叉点落子。
- 加入河界、九宫斜线与坐标映射。
- 黑方视角才翻转坐标；红方使用标准初始方向。
- 测试补充标准后排初始位置断言。

待真机确认：

- 车马相士将在标准交叉点上，炮和兵位置正确。
- 红黑视角翻转正确。
- 点击起点和终点不会偏一格。

### 斗兽棋

- 点击移动后立即显示目标位置的 pending 棋子反馈。
- 增加“正在确认落子 / AI 思考中”提示，避免网络请求期间像页面卡死。
- 棋盘最终状态仍以服务器响应为准，不做可能产生幽灵棋子的乐观改盘。
- 曾尝试修改后端 AI 性能，后来已经撤销，保持与线上后端兼容。

待真机确认：

- 点击己方棋子和目标格后立即显示反馈。
- AI 回合期间提示清楚，完成后棋盘正确同步。
- 多次点击不会重复提交动作。

## 4. 已完成的本地验证

在上述工作区状态下，最后已获得这些结果：

- 后端完整测试：`110 passed`（使用仓库内 `--basetemp`，规避 Windows 默认临时目录权限问题）。
- 小程序生产构建：`npm run build:weapp` 通过。
- 游戏测试：`npm run test:games` 通过。
- 斗地主横屏契约测试：`npm run test:landlord` 通过。
- `git diff --check` 通过；只有 Windows LF/CRLF 提示。
- 微信 CLI 预览包生成成功，包体约 `766.5 KB`（`784928` bytes）。

预览文件：

```text
D:\my-project\girlfriend-menu-app\miniprogram\dist\preview-2.11.2.png
D:\my-project\girlfriend-menu-app\miniprogram\dist\preview-2.11.2.json
```

注意：这只证明构建和预览包生成成功，不等于四页真机验收完成。

## 5. 微信开发者工具当前阻塞

开发者工具自动化端口曾使用：

- CLI 服务端口：`9421`
- automator 端口：`9330`

遇到的问题：

- `miniprogram-automator` 能建立 WebSocket，但 `systemInfo()`、`reLaunch()` 等 App 调用无响应。
- `npm run test:v24` 在冷启动或重新打开首页时超时。
- 临时 direct-acceptance 脚本也会挂起。
- 尝试通过 Windows GUI 控制组件检查开发者工具时，相关运行环境出现 `EPERM lstat`，所以不能把自动化连接成功误写成页面已确认。

建议下一窗口先做一次完全干净的开发者工具启动：

1. 关闭所有微信开发者工具进程。
2. 确认 9330、9421 不再监听。
3. 使用 CLI `auto` 或 GUI 重新打开 `miniprogram/`。
4. 等编译完全结束，再连接 automator。
5. 如果自动化仍无响应，改为开发者工具手工打开四页，并让用户用预览二维码做真机测试。

不要上传旧构建来绕过这个门槛。

## 6. 发布候选执行清单（2.11.2）

### A. 本地复核

```powershell
cd D:\my-project\girlfriend-menu-app
git status --short
git diff -- backend/tests/test_chess_engine.py miniprogram/src miniprogram/scripts
```

后端测试建议继续使用仓库内临时目录：

```powershell
cd D:\my-project\girlfriend-menu-app\backend
.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-release
```

小程序：

```powershell
cd D:\my-project\girlfriend-menu-app\miniprogram
npm run build:weapp
npm run test:games
npm run test:landlord
```

### B. 开发者工具四页验收

- 飞行棋：掷骰反馈、环形路线、事件格、移动结果。
- 斗地主：横屏、开始按钮、手牌和操作区。
- 中国象棋：标准初始位置、交叉点、双方坐标。
- 斗兽棋：落子即时反馈、AI 提示、服务端确认。

### C. 真机验收

用 `preview-2.11.2.png` 扫码。至少在一台真机逐页验收上面四项；涉及情侣房间的最终长期版仍建议用两台真机完成联机、断线、重连和重复动作检查。

### D. 通过后才允许发布

1. 把 `miniprogram/package.json` 和 `package-lock.json` 版本改为 `2.11.2`。
2. 更新 `CHANGELOG.md`、`README.md` 与 `docs/PROJECT_HANDOFF.md` 的版本和真实测试结论。
3. 提交本轮改动，建议提交信息：`improve four game mobile experiences for 2.11.2`。
4. 推送 `main`。
5. 等 Render 自动部署完成，检查 `/api/health` 和 `/api/ready`。
6. 用微信 CLI 上传开发版本 `2.11.2`。
7. 在微信公众平台“版本管理”把开发版本设为体验版。
8. 再做一次体验版真机回归。

浏览器、Render、Cloudflare 和微信公众平台曾在本窗口登录过，但新窗口不得假定登录会话仍有效；需要实际检查。

## 7. 关键架构现状

### 点餐主流程

保留且不得破坏：

```text
邀请码/设备会话
→ 菜单浏览与分类
→ 菜品详情/收藏
→ 点菜清单与备注/用餐时间
→ 提交订单
→ 我的点菜单/订单详情
→ 管理端改状态
→ 已完成订单爱心评价
→ 统计、积分和共同记录
```

### 小程序主要导航

```text
首页 / 菜单 / 点菜单 / 一起玩 / 我们
```

游戏与工具只放在“一起玩”，不能抢占点菜主流程。

### 身份与权限

- 普通端用后端设备会话 Bearer token；`gf_customer_id` 用于兼容旧设备身份。
- 管理端密码和邀请码由环境变量控制，不写死在前端。
- 关键变量名：`CUSTOMER_INVITE_CODE`、`ADMIN_PASSWORD`、`ADMIN_INVITE_CODE`、`ADMIN_SECRET`、`DATABASE_URL`。
- 不要把任何真实密码、邀请码、数据库连接串或对象存储密钥写进交接文档、Git 或小程序包。

### 数据与存储

- 订单、评价、收藏、积分、游戏记录、进行中游戏状态等落在 PostgreSQL。
- Render 本地 `uploads/` 不适合作为生产持久存储。
- 本窗口中曾尝试配置 Cloudflare R2，但没有完成 S3/R2 凭据。
- 后来项目改为私人部署默认使用 PostgreSQL 图片 provider，移除了 R2 作为体验版硬阻断；R2/S3 现在是图片规模扩大后的可选升级，不应再把“未配置 R2”直接等同于发布阻断。

### 游戏稳定化现状

`2.11.0/2.11.1` 已完成的核心工程能力：

- 实时游戏快照写入 PostgreSQL，Redis 仅为可选热缓存。
- 多实例房间用 PostgreSQL 租约确定唯一写入实例。
- WebSocket 自动重连、指数退避、抖动和有界离线消息队列。
- 大话骰重连按查看者过滤，开盅前不泄露对手骰子。
- 结算有 pending/complete/failed 与补偿扫描。
- 幽灵房间可过期为 abandoned。
- HTTP 回合制动作使用 `client_action_id` 幂等。
- 斗兽棋和象棋增加回合超时、重复局面、无进展/最大步数和棋。
- Phase 2A/2B/2C 已逐步拆分 Router、Service/Repository 与实时运行时边界。

仍需长期观察：

- Render 冷启动和生产 WebSocket 首包延迟。
- 多实例切换依赖客户端重连，不是无缝迁移。
- 两台真机的完整联机/断线/重连验收证据。
- 随游戏数据增大后的归档、备份、监控和对象存储迁移。

## 8. 本窗口需求与版本演进摘要

### 最初 MVP 与网页部署

项目从 React + Vite 网页端、FastAPI、SQLite 的“女朋友专属点菜”MVP 开始，先后增加：

- 图片上传与 `/uploads` 静态访问。
- 爱心评价和评价统计。
- 管理端订单统计。
- 管理密码登录。
- `customer_id` 本地身份与“我的点菜单”。
- PostgreSQL/环境变量/CORS/Render/Vercel 线上化。

随后项目迁移重点到 Taro 微信小程序；旧 React/Vite 网页端最终退休并从当前结构清理。

### 微信小程序阶段

- 新增 Taro React 小程序端并复用 FastAPI API。
- 增加邀请码准入、手机端 UI 修正、订单/评价/管理流程。
- 曾尝试把网页 3D 骰子通过 `web-view` 搬进小程序，但个人主体缺少业务域名能力，最终回到原生小程序游戏实现。
- 游戏统一归入“一起玩”，管理入口降低强调，点菜保持主任务。

### V2.0～V2.8 产品扩展

- V2.0：五主导航、收藏、再次点单、菜品标签、喜爱排行和 UI 统一。
- V2.2：情侣积分、默契值、成就和共同记录。
- V2.3：统一游戏大厅、房间、WebSocket 和双人五子棋。
- V2.4：飞行棋、互动事件、每日任务。
- V2.5：斗地主、斗兽棋和 AI 基础。
- V2.6：中国象棋、游戏排行、回放/记录和规则型陪伴摘要。
- V2.7：统一用户、通知、情侣档案/时间轴/纪念日及系统稳定化。
- V2.8：安全、发布、备份、正式上线收口。

### 2.9～2.11 游戏质量与架构优化

- 2.9.0/2.9.1：体验版发布、全模式人机与网络轮询优化。
- 2.9.2：参考许可证清晰的 GitHub 项目改善各游戏规则/AI；不复制商业产品商标、美术和音效。
- 2.9.3：斗地主改为熟悉的横屏牌桌层级。
- 2.10.0：长期稳定化、恢复、同步状态条、WebSocket 自动重连、持久快照与隐私修复。
- 2.11.0：多实例租约、结算补偿、房间过期、动作幂等、超时和和棋规则。
- 2.11.1：Phase 2C Round 3 实时边界拆分、生产重连修复和动作延迟优化，已提交并作为当前基线。
- 2.11.2（候选）：本地正在处理飞行棋、斗地主、象棋、斗兽棋的手机体验问题，尚未发布。

## 9. 参考与许可证边界

曾调研并只借鉴架构/交互思想的开源项目包括：

- `boardgame.io`（MIT）：纯状态转移、阶段/回合、日志和服务端同步。
- `GomokuZero`（MIT）：五子棋候选排序和搜索思路。
- `RLCard`（MIT）、`DouZero`（Apache-2.0）：斗地主状态、合法动作和 AI 评测思想。
- `ludo-js`（MIT）：飞行棋状态机、六点/移动/吃子规则。
- `jungle-chess`（MIT）：斗兽棋规则和网络房间思路。
- `xiangqi` React 案例（MIT）：象棋记录、AI 和 UI 分层思路。
- `dice-box`（MIT）：骰子物理状态与表现分离。
- `spin-wheel`（MIT）：转盘触摸、惯性和落点回调。

不得复制 JJ 斗地主或其他商业产品的商标、美术、音效和受版权保护素材。实际复制任何开源代码时必须检查并保留相应许可证；当前方向主要是独立实现。

## 10. 文档入口

新窗口应优先阅读：

1. `docs/PROJECT_HANDOFF.md`：当前架构、页面、模型、API 和部署事实。
2. `README.md`：本地运行、部署、域名和验收流程。
3. `docs/GAME_RUNTIME_STABILITY_2_11_0.md`：游戏长期稳定机制。
4. `docs/optimization/PHASE_2C_GAME_RUNTIME_REVIEW.md`：实时边界与生产测试记录。
5. `docs/CAPABILITY_MATRIX.md`：能力与验收覆盖。
6. `docs/RELEASE_CHECKLIST_V2_9.md`：旧体验版发布记录（只作历史参考）。
7. 本文：当前未提交四游戏修复与下一步发布门槛。

## 11. 给新窗口 Codex 的建议开场指令

可以直接粘贴：

```text
请先阅读：
D:\my-project\girlfriend-menu-app\docs\THREAD_HANDOFF_2026-08-12.md
D:\my-project\girlfriend-menu-app\docs\PROJECT_HANDOFF.md

然后检查 git status 和未提交 diff。不要覆盖当前工作区。
继续完成 2.11.2 候选版验收：先解决微信开发者工具自动化无响应，在开发者工具和真机确认飞行棋、斗地主、中国象棋、斗兽棋四页；只有确认通过后，才更新版本、完整测试、提交、推送并上传微信体验版。所有发布结论必须有实际证据。
```

## 12. 2026-08-12 续接进展（本窗口）

本窗口已完成以下工作，仍不得误写为真机验收或体验版发布：

- 清理会无限挂起的临时 `game-pages-direct-acceptance.cjs`，改为有界超时的 `game-pages-devtools-acceptance.cjs`。
- 修复 V2.4～V2.7 冒烟脚本的 tabBar 导航与离线设备会话，使页面守卫不会误把结构测试重定向回首页。
- 微信 CLI 需要显式传入 `--auto-port 9330`，且应等待 9330 实际开始监听后再运行 automator；CLI 返回 `auto` 不代表端口已经就绪。
- 开发者工具结构验收已通过：飞行棋、斗地主、斗兽棋、中国象棋四页均能打开，稳定入口与关键控件存在。
- 当前开发者工具版本的 `App.captureScreenshot` 会超时，因此没有把截图失败冒充视觉验收；页面结构通过不等于真机交互通过。
- 额外修正飞行棋第 24 格文案，使其与服务端 `FOOD` 事件一致；修正象棋九宫斜线长度。没有修改后端规则或 API。
- 验证结果：后端 `110 passed`；`npm run build:weapp`、`npm run test:games`、`npm run test:landlord`、`npm run test:v24`、`npm run test:v25`、`npm run test:v26` 和 `npm run test:game-pages:devtools` 均通过；`git diff --check` 通过（只有 LF/CRLF 提示）。
- 已基于最新构建重新生成预览二维码：`miniprogram/dist/preview-2.11.2.png`，包体 `784998` bytes，生成时间 `2026-08-12 21:57:33`。

当前唯一发布阻断仍是用户真机逐页验收。版本号仍为 `2.11.1`；未提交、未推送、未上传开发版，也未设置体验版。真机四页确认通过后，才执行第 6 节 D 的发布步骤。

## 13. 交互体验第二轮优化

用户反馈四个游戏“交互体验感很差”后，本窗口继续完成了以下未发布改动：

- 新增共享 `GameTurnGuide`，把“当前发生了什么 / 下一步点哪里”固定放到大棋盘之前；忙碌、同步、离线、等待对方、已选棋子等状态使用一致的文案和颜色。
- 情侣房等待状态提供直接的微信分享邀请按钮，减少复制房间码后再手动找人的步骤。
- 飞行棋把骰子移动到棋盘前，只有在线且轮到自己时才可掷；棋盘仍以服务端结果为准。
- 中国象棋与斗兽棋支持再次点击已选棋子取消选择，落子请求期间立即显示目标位置反馈，并在断网时禁止继续提交动作。
- 斗地主区分“轮到你 / 等待对方 / 先选牌 / 正在提交”，并按照后端规则只在可以不跟首手牌时开放“不出”。等待好友时可以一键分享房间。
- 四个大厅压缩了占屏过大的装饰头图，加强主操作按钮的按压反馈，让模式、难度和开始入口更早出现在首屏。
- `game-pages-devtools-acceptance.cjs` 已增加真实点击“人机模式”并检查选中反馈的逻辑，但本轮启动微信开发者工具的外部执行权限被拒绝，所以新交互尚未完成开发者工具自动点击验收，不得写成已通过。
- 最新本地验证：`npm run build:weapp`、`npm run test:games`、`npm run test:landlord` 通过；`git diff --check` 通过（只有 LF/CRLF 提示）。本轮没有修改后端业务逻辑，沿用此前后端 `110 passed` 的结果。

重要：`miniprogram/dist/preview-2.11.2.png` 生成于本轮交互改造之前，已经不是最新代码的二维码，不能用于最终验收。需要在获得微信 CLI 执行许可后重新生成，再进行开发者工具与真机验收。版本号仍为 `2.11.1`，未提交、未推送、未上传。

## 14. 最新开发者工具点击验收与预览包

用户明确允许启动微信开发者工具后，已完成：

- `npm run test:game-pages:devtools` 通过。脚本依次直接打开飞行棋、斗地主、斗兽棋、中国象棋大厅，真实点击第二个模式选项，并断言该选项获得 `active` 选中状态；有人机难度的页面同时断言难度控件出现。
- 四页结果均为 `PASS`。当前 DevTools 的 `App.captureScreenshot` 仍会超时，因此这里只能证明页面结构和上述点击反馈，不能替代真机视觉、完整创建房间或对局验收。
- 微信 CLI 已在最终构建与本地回归之后重新生成 `miniprogram/dist/preview-2.11.2.png` 与 `preview-2.11.2.json`，最终时间为 `2026-08-12 23:49:45`，小程序包体 `793253` bytes（`774.7 KB`），二维码文件 `47416` bytes。
- 重新尝试旧版 V2.4/V2.5 综合脚本时，当前 DevTools/automator 在 `pages/games/index` tabBar 页面返回路径正确但节点树为空；源码与最新编译产物都包含 `.game-library-grid`/`.v25-game-grid`。这属于旧综合脚本/工具兼容问题，不得写成游戏大厅结构已通过，也不能反推四个专项游戏页失败。为定位而做的临时探针已撤除。

先前第 13 节关于二维码“已经过期”的描述现已被本节取代：23:49:45 生成的二维码是当前最新候选代码。版本号仍为 `2.11.1`，未提交、未推送、未上传开发版；下一步仍是真机扫码检查首屏信息层级、分享入口、落子/掷骰反馈及斗地主横屏操作区。

## 15. 2026-08-13 真机反馈修复

用户提供真机截图，确认两个具体问题：斗地主大厅无法点击开局，中国象棋顶部和底部棋子被裁成半枚。已完成以下修复：

- 斗地主根节点使用 Grid，而原先的 `PageMeta` 是 Grid 的第一个子项，实际占用了第一个格子，导致主视觉被排到右上、配置卡被挤到左下并超出横屏视口。现在 `PageMeta` 位于 Fragment 中、布局容器之外；同时把 `.ll-hero` 固定在第一列、`.ll-lobby-card` 固定在第二列的同一行。
- 象棋不是棋子数据缺失，而是第 0/9 行棋子的中心位于线网边界，半枚棋子超出容器后被 `overflow:hidden` 裁切。现在将线网宽度调整为 `82%`，上下安全边距调整为 `5.5%`，为四条边上的完整棋子预留空间，服务端坐标与点击映射不变。
- 增加防回归契约：斗地主禁止 `PageMeta` 再次进入 Grid，并要求主视觉/开局卡固定同一行；象棋要求保留边缘棋子安全区。
- 最新验证：`npm run build:weapp`、`npm run test:games`、`npm run test:landlord`、`npm run test:game-pages:devtools` 和 `git diff --check` 通过。四个游戏专项页面仍能打开并切换人机模式；斗地主开局按钮存在完整可查询点击区域。

重要：第 14 节 23:49:45 的二维码生成于本节修复之前，现已过期。尝试重新生成时，安全审批指出微信 `preview` 会把当前私有项目包上传到微信服务，而用户只明确授权了启动开发者工具验收，因此未执行上传。必须在用户明确同意“将当前小程序包上传到微信预览服务并生成二维码”后才能继续。

## 16. 象棋竖线修复

用户继续反馈象棋棋盘缺少竖线。检查后确认旧实现用单个 CSS 渐变模拟 9 条竖线的河界断点，同时在其上覆盖一块不透明河界背景；微信真机对渐变断点的渲染以及河界遮罩会让竖线视觉缺失。

- 现在每一条竖线都使用真实节点绘制，不再依赖渐变断点。
- 最左、最右两条边线完整贯通；中间 7 条竖线分别绘制河界上段和下段，河界处按标准象棋棋盘断开。
- “楚河 / 漢界”改为透明文字层，不再使用不透明背景覆盖线网。
- 服务端棋局坐标、红黑视角翻转、落子映射和规则均未修改。
- 防回归契约要求编译前源码必须包含 `full/top/bottom` 三类真实竖线结构，并禁止河界不透明遮线。

最新本地结果：`npm run build:weapp`、`npm run test:games`、`npm run test:landlord` 和 `git diff --check` 通过；编译后的 `dist/pages/games/chess/index.js` 已确认包含新的 9 列真实竖线结构。随后两次四页 DevTools 回归均在第一站飞行棋拿不到节点树；加入页面过滤后单独打开象棋也拿不到节点树，因此判断为当前 DevTools/automator 节点树异常。这一轮不能写成开发者工具视觉验收通过。

本次构建会清空 `dist`，此前二维码已不存在且本来也早于本节修复。生成可供真机复核的新二维码仍需用户明确授权把当前私有小程序包上传到微信预览服务。

## 17. 最新微信预览包（已获授权）

用户随后明确允许“将当前小程序包上传到微信预览服务并生成二维码”。已基于包含斗地主大厅布局修复、象棋棋子安全边距与真实竖线结构的最新构建执行微信 CLI `preview`，微信侧返回 `preview` 成功。

- 生成时间：`2026-08-13 00:20:00`
- 小程序包体：`793253` bytes（`774.7 KB`）
- 二维码：`miniprogram/dist/preview-2.11.2.png`，文件大小 `47205` bytes
- 预览信息：`miniprogram/dist/preview-2.11.2.json`
- AppID 权限检查通过：`wx08cb090781c3e679`

本节取代第 16 节末尾“等待上传授权”的状态。这里只完成了微信预览服务上传和二维码生成，不等于上传开发版本、设置体验版或正式发布；下一步仍需真机扫码检查斗地主开局入口和象棋完整棋盘。

## 18. 斗地主首屏重构与象棋线网加固

用户再次要求自由优化游戏，并明确指出斗地主页面布置不合理、无法点击开局，以及象棋竖线不全。本轮未修改 API、服务端规则或象棋坐标语义，主要完成以下前端收口：

- 斗地主把主操作改为微信原生 `Button`，并移动到配置卡标题之后、所有设置项之前；进入页面后无需先阅读或滚动即可看到“创建牌桌 / 立即开局”。
- 配置卡增加横屏视口上限，低高度和极低高度设备会逐级压缩说明文字与非关键间距，但不会隐藏开局按钮；左侧标题保持单行。
- 开局按钮拥有独立禁用态、按压态和约 `485 × 65` 的开发者工具点击区域，设置项与加入房间降为第二层操作。
- 象棋继续使用 9 列真实竖线节点，并把线宽提高到 `3px`、颜色改为高对比度深棕、提升独立线网层级；河界文字保持透明背景。
- 象棋线网结构为 9 列、10 条横线、2 条贯通边线，以及河界上下各 7 条中间竖线，符合标准棋盘断线方式。
- 开发者工具斗地主验收：横屏根容器 `844 × 390`，主按钮位于 `(313, 100)`、尺寸 `485 × 65`，完整在视口内；真实点击通过。
- 使用隔离的本地 SQLite 和测试设备会话完成业务闭环：斗地主 `POST /api/games/landlord/create` 返回 `201` 并进入 `.ll-room`；象棋 `POST /api/games/chess/create` 返回 `201`，页面实际渲染并数到完整线网，截图人工复核竖线完整。
- 临时本地验收数据库已删除；`project.config.json` 已恢复 `urlCheck: true`；最终 `dist` 不包含 `127.0.0.1:8000`，只包含生产 API 地址，也不包含验收截图目录。
- 最终正式构建及回归通过：`npm run build:weapp`、`npm run test:landlord`、`npm run test:games`、`git diff --check`。两条旧版 V2.5/V2.6 脚本曾因并发争抢微信 IDE 端口而未启动成功，不能写成通过，但本轮针对斗地主与象棋的专项开发者工具验收已完成。

验收证据存放在忽略目录 `miniprogram/.test-tmp/acceptance-2.11.2/`，不会打入小程序包。由于本轮又生成了不同于第 17 节的新构建，安全审批没有自动沿用旧包上传授权，因此尚未把这一份更新后的包再次上传微信预览服务；需要用户针对这份更新包重新明确授权后再生成二维码。

## 19. 本轮优化包微信预览已上传

用户已针对第 18 节完成后的最新构建明确授权上传微信预览服务。上传前再次核对：`urlCheck: true`、编译产物没有 `127.0.0.1:8000`、只包含生产 API 地址、`dist` 不含验收截图；`npm run test:landlord`、`npm run test:games` 与 `git diff --check` 通过。

- 微信 CLI 返回：`preview` 成功
- AppID：`wx08cb090781c3e679`
- 生成时间：`2026-08-13 09:30:07`
- 小程序包体：`794903` bytes（`776.3 KB`）
- 二维码：`miniprogram/.test-tmp/preview-2.11.2-games-optimized.png`，`47530` bytes
- 预览信息：`miniprogram/.test-tmp/preview-2.11.2-games-optimized.json`

该二维码包含斗地主首屏原生开局按钮、真实建局链路修复，以及象棋完整高对比度线网。这里只完成微信预览上传与二维码生成；未上传开发版本、未设置体验版，也未正式发布。下一步是真机扫码复核斗地主横屏开局和象棋完整竖线。
