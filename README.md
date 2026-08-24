# 情侣智能厨房管家

这是一个面向情侣私厨场景的微信点菜小程序：她负责选菜、提交点菜单和评价，你通过同一个小程序里的管理端查看订单、更新制作状态和维护菜单。

当前产品界面只保留微信小程序。早期 React/Vite 网页端及其停用占位页已从仓库删除，不再作为构建或部署入口。

## 当前版本与线上状态

- 当前源码版本：`3.0.0`（LoveOS V3 渐进式重构功能分支）
- 当前微信体验版：`2.11.2`（2026-08-17 构建并上传）
- AppID：`wx08cb090781c3e679`
- 后端：FastAPI，部署于 Render
- 生产数据库：Neon PostgreSQL
- 生产 API：`https://girlfriend-menu-api.onrender.com`
- 2026-08-08 验证结果：API 健康检查正常、数据库为 PostgreSQL、线上有 19 道启用菜品

后端模块化状态：Phase 2A 已将 Router 从 `main.py` 拆分；Phase 2B 已将 Dish、
Favorite、Review、Order 与非游戏 Stats 收敛为
`Router -> Service -> Repository`，并保留 `crud.py` 兼容门面。喜欢排行榜以及
游戏/实时持久化不在 Phase 2B 范围。Phase 2C Round 1 已抽出游戏目录、房间、
玩家、房间会话与记录的持久化边界；Round 2 又抽出 WebSocket 会话编排与幂等
结算服务。协议收发、关闭码、实时 Manager、数据库和公开接口均未变化。

## 已实现功能

女朋友端：

- 邀请码进入
- “首页、菜单、点菜单、一起玩、我们”五个主导航
- 菜品列表、分类筛选、菜品详情、制作信息和标签
- 点菜清单、数量修改、备注、希望用餐时间、提交订单
- “我的点菜单”、订单状态与历史记录、“再做一次”可编辑草稿
- 按当前设备保存的菜品收藏
- 根据点单、评价、收藏和再次点单计算“她最喜欢”Top 5
- 已完成订单的 1～5 颗爱心评价
- 自定义选项转盘
- 单机 3D 大话骰（原生 WebGL 场景、AI 玩家、上滑开盅）
- 克制的统一游戏大厅、动态游戏目录、未完房间直达恢复和维护状态
- 双人实时大话骰房间、叫骰、开盅与计分板
- 15×15 双人/人机五子棋、服务端落子校验、五连胜负判定和再来一局
- 双人/人机飞行棋、服务端掷骰、四棋子移动、碰撞、精确到达与持久棋局状态
- 飞行棋爱心/厨房/快乐/挑战随机事件，完成后自动记录互动与默契积分
- 每日情侣任务、完成进度、自动触发与最近互动记录
- 情侣斗地主：两位真人 + AI 或单人 + 两个 AI，服务端洗牌发牌、私有手牌、叫地主与完整出牌校验
- 斗兽棋：标准 7×9 棋盘、情侣房间、单人 AI、河流/陷阱/兽穴规则
- V2.5 游戏统一核心、持久 `game_sessions`、乐观版本锁和房间聊天状态
- 持久成就目录、解锁奖励与斗地主局后情侣约定
- 中国象棋双人/AI 对局：标准 9×10 棋盘、服务端规则、将军与棋谱回放
- 游戏数据中心：个人战绩、共同房间月榜、AI 角色目录和私人游戏记忆
- 统一用户档案：旧 `customer_id` 可恢复为有期限、可轮换、可撤销的设备会话，不丢历史订单与互动记录
- 订单、游戏加入/完成和纪念日站内通知
- “我们的故事”时间轴、手写共同记忆、纪念日与提前提醒
- 未完成游戏发现、哈希重连凭证和通用对局回放
- 大话骰与五子棋进行中快照持久化到 PostgreSQL；Redis 仅作为可选热缓存和在线标记
- 实时游戏指数退避自动重连、有限离线队列；回合制页面显示同步/离线/重试状态
- 可解释的每日陪伴小结：只使用真实点菜、游戏与默契数据
- 通用 `/ws/game/{room_code}` 房间通信协议
- “我们”情侣中心、默契值、积分流水、共同记录和成就展示
- “我们的游戏记录”按设备查看五子棋历史、胜负、局数和时长
- 完成订单、五星评价和“再做一次”自动累计情侣积分
- 五子棋完成一局、获胜和三连胜自动累计情侣积分

小程序管理端：

- 管理密码登录与退出
- 实时查看订单、备注和希望用餐时间
- 修改订单状态：待接单、已接单、制作中、已完成、暂时做不了
- 新增、编辑、下架菜品
- 维护制作时间、难度、辣度和菜品标签
- 上传菜品图片或手动填写图片链接
- 总订单、已完成订单、最常点菜品、最近订单、平均评分和评价记录统计
- 总游戏次数、五子棋/飞行棋/斗地主/斗兽棋、AI 对局、真人胜率、成就和近 7 天默契增长统计
- 今日订单、今日游戏、默契增长、热门菜与热门游戏驾驶舱

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 微信小程序 | Taro 4、React 18、微信原生 Canvas/WebGL |
| 后端 API | Python 3.12、FastAPI、Pydantic 2 |
| 数据访问 | SQLAlchemy 2 |
| 生产数据库 | Neon PostgreSQL |
| 本地数据库 | SQLite（未配置 `DATABASE_URL` 时） |
| 实时通信 | FastAPI WebSocket（管理订单推送、大话骰与五子棋双人房间） |
| 游戏状态 | PostgreSQL 权威快照；Redis 可选热缓存（未配置时不丢进行中棋局） |
| 部署 | Render Blueprint + GitHub 自动部署 |
| 自动化 | Pytest、GitHub Actions、微信开发者工具自动化冒烟脚本 |

## 项目结构

```text
girlfriend-menu-app/
├── .github/workflows/ci.yml     # 后端测试与小程序构建
├── backend/                     # FastAPI、SQLAlchemy、实时房间
│   ├── main.py                  # HTTP/WebSocket 路由、鉴权、生命周期
│   ├── crud.py                  # 兼容门面、跨域排行榜与游戏持久化
│   ├── services/                # 非游戏业务规则和事务后编排
│   ├── repositories/            # 非游戏 SQLAlchemy 查询与持久化
│   ├── database.py              # PostgreSQL/SQLite 连接与兼容升级
│   ├── alembic/                 # 正式数据库迁移版本
│   ├── alembic.ini              # Alembic 配置
│   ├── models.py                # SQLAlchemy 数据模型
│   ├── schemas.py               # API 请求/响应模型
│   ├── realtime.py              # 订单事件与统一双人游戏房间
│   ├── core/cache.py             # 可选 Redis 热状态与在线 TTL
│   ├── user_service.py           # 兼容旧 customer_id 的统一身份
│   ├── notification_service.py   # 订单、游戏、纪念日消息
│   ├── couple_profile_service.py # 时间轴、纪念日与情侣统计
│   ├── game_recovery_service.py  # 重连令牌、继续游戏与回放
│   ├── gomoku.py                # 服务端权威五子棋规则引擎
│   ├── flight.py                # 可测试的飞行棋规则引擎
│   ├── flight_service.py        # 飞行棋持久化、事件与结算编排
│   ├── games/core/              # V2.5 统一引擎、玩家、房间与版本状态
│   ├── games/landlord/          # 斗地主牌组、牌型、发牌、AI 与引擎
│   ├── games/animal/            # 斗兽棋棋盘、规则、AI 与引擎
│   ├── ai/                      # 可替换 random/rule/strategy AI 协议
│   ├── task_service.py          # 每日任务生成和防重复奖励
│   ├── alembic/versions/        # V2.0～V2.5 数据库版本
│   ├── seed.py                  # 19 道测试菜品
│   ├── storage.py               # 本地图片存储
│   └── tests/                   # 后端主流程、游戏与情侣积分测试
├── miniprogram/                 # Taro React 微信小程序（主产品）
│   ├── config/                  # Taro 构建配置
│   ├── scripts/smoke-test.cjs   # 微信开发者工具冒烟测试
│   ├── src/api/                 # HTTP 与 WebSocket 客户端
│   ├── src/components/          # 共享导航、棋盘、牌桌与游戏组件
│   ├── src/pages/               # 用户端、管理端与全部游戏页面
│   ├── src/utils/               # 邀请码、购物车、设备身份、管理令牌
│   ├── project.config.json      # 微信项目配置
│   └── package.json
├── docs/PROJECT_HANDOFF.md      # 完整产品、架构、数据和审计交接
├── render.yaml                  # Render 后端部署蓝图
└── README.md
```

## 本地运行

### 1. 启动后端

要求 Python 3.12。

Windows CMD：

```bat
cd /d D:\my-project\girlfriend-menu-app\backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

本地环境变量示例在 `backend/.env.example`。未配置 `DATABASE_URL` 时会使用 `backend/girlfriend_menu.db`。

启动后检查：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/ready
http://127.0.0.1:8000/docs
```

`/api/ready` 保持 HTTP 200，通过顶层 `status` 表示是否可发布；`authentication.missing` 只列出缺失或不可用的配置项名称，不包含密码、邀请码或散列值。

如果 Windows 对 8000 端口报 `WinError 10013`，可改用 8010：

```bat
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload --no-access-log
```

小程序当前固定请求生产 API。若要联调本机后端，需要把 `miniprogram/src/api/index.js` 中的 API 地址临时改为手机或开发者工具能够访问的 HTTPS 地址；真机不能直接访问电脑的 `localhost`。

### 2. 构建小程序

要求 Node.js 22。

```bat
cd /d D:\my-project\girlfriend-menu-app\miniprogram
npm install
npm run build:weapp
```

用微信开发者工具导入：

```text
D:\my-project\girlfriend-menu-app\miniprogram
```

`project.config.json` 已配置 AppID，并把小程序根目录指向 `dist/`。持续开发时可运行：

```bat
npm run dev:weapp
```

## 自动测试

后端：

```bat
cd /d D:\my-project\girlfriend-menu-app\backend
.venv\Scripts\python.exe -m ruff check . ..\scripts
.venv\Scripts\python.exe -m pytest -q
```

小程序编译：

```bat
cd /d D:\my-project\girlfriend-menu-app\miniprogram
npm run build:weapp
```

微信开发者工具冒烟测试依赖本机开发者工具路径和已开启的服务端口；当前脚本入口为：

```bat
npm run test:smoke
npm run test:v24
npm run test:v25
npm run test:v26
npm run test:v27
npm run test:games
npm run test:ci
```

2026-08-11 本地验证：后端 `79 passed`、设备会话迁移/恢复/撤销、实时状态重启/骰子隐私、Socket 生命周期与游戏恢复契约通过，小程序生产构建通过。

## 数据库

核心表：

- `dishes`：菜品、分类、价格、图片、制作时间、难度、辣度、标签、启用状态
- `orders`：订单状态、备注、希望用餐时间、设备 `customer_id`、再次点单来源
- `order_items`：下单时的菜名和价格快照、数量
- `reviews`：每个订单唯一的一条爱心评价
- `customers`：兼容旧 `customer_id` 的稳定客户档案；旧 token 哈希暂留作迁移桥
- `customer_sessions`：有期限、可轮换、可撤销的设备会话，只保存 token 哈希
- `favorite_dishes`：按 `customer_id + dish_id` 唯一保存收藏
- `games`：游戏名称、图标、类型与开放状态
- `game_rooms`：房间码、游戏类型、创建者、房间状态、最大人数和完成时间
- `game_players`：每个房间的持久玩家席位、设备标识、局分和加入时间
- `game_states`：飞行棋、大话骰和五子棋进行中的权威 JSONB/JSON 快照
- `game_sessions`：斗地主和斗兽棋的权威 JSONB/JSON 状态、当前回合与版本
- `game_events` / `game_event_logs`：随机互动目录和实际完成记录
- `daily_tasks`：按设备、日期和任务类型唯一的今日任务
- `game_records`：每个房间每一局的胜者、时长和服务端结果快照
- `achievements` / `user_achievements`：成就定义和按设备的解锁记录
- `love_tasks`：斗地主完成后生成的情侣约定
- `love_scores`：按设备记录积分、行为类型、描述、关联业务编号和发生时间
- `users`：统一的客户、管理员和 AI 身份映射
- `notifications`：订单、游戏与纪念日站内通知
- `couple_memories` / `couple_dates`：共同时间轴和纪念日
- `game_reconnect_tokens`：只保存哈希的过期重连凭证
- `game_replays`：跨游戏的服务端结果和步骤快照

V2.0 使用 Alembic 管理数据库版本。部署启动会先执行迁移，再启动 API；迁移只新增表、字段和索引，不删除或重建旧订单数据。程序内仍保留幂等兼容检查，方便旧的本地 SQLite 直接启动。

后端路由已按职责拆分到 `backend/api/routes/`。`main.py` 只负责应用生命周期、中间件、静态目录和总 Router 注册；认证依赖统一位于 `backend/api/dependencies.py`。本次模块化没有改变任何 API、模型或迁移，完整审查见 [Phase 2A Router 模块化](docs/optimization/PHASE_2A_ROUTER_REVIEW.md)。

完整字段和关系见 `docs/PROJECT_HANDOFF.md`。

V2.7 架构、API、Redis 降级边界和部署说明见 `docs/V27_STABILITY_COUPLE_PROFILE.md`。

LoveOS V3 微信身份、数据库管理账号、首屏生产化、部署/回滚和发布门禁见 [V3 生产化发布包](docs/release-v3/README.md)。

## 生产部署

### Render + Neon PostgreSQL

Render 只部署 `backend/`，构建和启动命令已经写在 `render.yaml`：

```text
pip install -r requirements.txt
python serve.py
```

三个 Blueprint 都保持 Render 免费计划。生产 `autoDeploy=false`，只能在备份、隔离恢复和候选提交门禁通过后手动发布。`serve.py` 会先检查数据库版本与参考数据；只在首次部署或发现漂移时执行迁移与幂等修复，然后在同一进程启动 Uvicorn。

生产环境必须配置：

| 变量 | 用途 |
| --- | --- |
| `DATABASE_URL` | Neon PostgreSQL 连接串 |
| `CUSTOMER_INVITE_CODE` | 普通端新建设备会话与找回旧身份使用的邀请码；必须与管理凭据分离 |
| `CUSTOMER_SESSION_TTL_DAYS` | 设备会话有效期，默认 90 天，可配置 1～365 天 |
| `ADMIN_PASSWORD` | 仅兼容迁移时显式配置；新部署优先使用下方散列 |
| `ADMIN_PASSWORD_HASH` | 推荐：由 `python scripts/hash_admin_password.py` 生成的 scrypt 启动散列 |
| `ADMIN_INVITE_CODE` | 显式生成的管理邀请码，必须与客户邀请码不同 |
| `ADMIN_SECRET` | 用 `secrets.token_urlsafe(48)` 显式生成的独立令牌签名密钥 |
| `WECHAT_LOGIN_ENABLED` | 微信身份恢复发布开关；凭据就绪并完成体验版验收后设为 `true` |
| `WECHAT_APP_ID` | 微信小程序 AppID |
| `WECHAT_APP_SECRET` | 仅后端保存的 AppSecret，严禁写入小程序或提交到 Git |

可选变量：

| 变量 | 用途 |
| --- | --- |
| `FRONTEND_URL` | 未来获准浏览器客户端的 CORS 域名；微信小程序无需配置 |
| `UPLOAD_PROVIDER` | `database`（私人部署默认）或 `s3`；生产环境不可使用 `local` |
| `REDIS_URL` | 可选的跨进程缓存、限流与热状态协调；单实例可安全降级 |

`backend/.env.example` 中的所有秘密字段故意留空。管理密码散列由 `python scripts/hash_admin_password.py` 在本机生成；`ADMIN_SECRET`、管理邀请码和客户邀请码需分别使用 Python `secrets` 显式生成。不要把生产 `.env`、Neon 密码或管理密码提交到 GitHub 或放进项目压缩包。

### 微信公众平台服务器域名

在“开发管理 → 开发设置 → 服务器域名”配置：

| 类型 | 域名 |
| --- | --- |
| request 合法域名 | `https://girlfriend-menu-api.onrender.com` |
| socket 合法域名 | `wss://girlfriend-menu-api.onrender.com` |
| uploadFile 合法域名 | `https://girlfriend-menu-api.onrender.com` |
| downloadFile 合法域名 | `https://girlfriend-menu-api.onrender.com` |

域名末尾不要添加 `/api`、路径、端口或分号。

## 预览、体验版和正式发布

1. 在 `miniprogram/` 执行 `npm run build:weapp`。
2. 微信开发者工具打开 `miniprogram/` 并点击“编译”。
3. 点击“预览”，用真机走完下方验收流程。
4. 点击“上传”，V2.6 开发版本号使用 `2.6.0`。
5. 微信公众平台进入“版本管理”，把开发版本选为体验版。
6. 体验无误后提交微信审核；审核通过后再正式发布。

## 核心验收流程

1. 清理小程序缓存，输入邀请码，确认首页只突出推荐、常点和今日菜单。
2. 通过底部“菜单”筛选分类，打开详情，收藏一道菜并加入清单。
3. 填写备注和希望用餐时间，提交订单。
4. 从“点菜单”进入历史记录，点击“再做一次”，确认菜品和数量进入可编辑清单，确认后再提交。
5. 进入“我们”查看默契值、积分明细、共同记录、成就与原有口味收藏，并从低强调入口进入“小厨房管理”。
6. 管理端确认新订单实时出现，把状态改为“已完成”。
7. 回到订单详情提交爱心评价，再次进入时只能看到评价结果。
8. 返回首页，确认“她最喜欢”排行已根据当前设备数据更新。
9. 管理端编辑菜品制作时间、难度、辣度和标签，并检查统计与评价记录。
10. 通过“一起玩”分别测试大话骰、五子棋、飞行棋、斗地主、斗兽棋和中国象棋的人机模式，再用两台手机测试情侣房间；检查飞行棋骰子与所有 AI 行动均由服务端生成（单机 3D 大话骰为本地 AI）。
11. 完成订单后检查情侣积分增加 10 分；提交五星评价后再增加 5 分，并确认重复修改状态不会重复计分。
12. 完成一局五子棋或飞行棋后，双方各增加 1 分，胜者再增加 5 分；首次完成当天游戏还会点亮每日任务并增加 3 分。
13. 进入“我们 → 每日任务”，手动完成夸奖任务；再完成订单、五星评价和双人游戏，确认其余任务由后端自动点亮且不会重复加分。
14. 两台设备创建/加入斗地主，确认彼此看不到手牌、AI 自动行动、过期操作不会覆盖牌局；结束后检查成就和情侣约定。
15. 分别测试斗兽棋情侣房间与 AI 模式，确认普通棋子不能下水、狮虎可跳河、进入对方兽穴结束。

## V2.1 统一游戏中心

游戏大厅通过 `GET /api/games` 获取目录。只有 `status=available` 的游戏可以创建房间；当前大话骰、五子棋、飞行棋、斗地主、斗兽棋和中国象棋均已开放。

新房间通过 `POST /api/games/rooms` 创建，实时连接统一使用：

```text
wss://girlfriend-menu-api.onrender.com/ws/game/{room_code}
```

现有 `/api/games/dice/rooms` 与 `/ws/games/dice/{room_code}` 保留兼容，已经上传的旧小程序不会因后端升级立即失效。协议细节见 [游戏中心通信协议](docs/GAME_CENTER_PROTOCOL.md)。

## V2.2 情侣积分系统

底部“我们”是情侣成长中心。积分由后端业务事件自动写入：订单首次变为“已完成”增加 10 分，五星评价增加 5 分，通过“再做一次”提交新订单增加 2 分。相同订单与相同行为使用唯一来源约束，重复修改状态不会重复加分。

积分总数用于记录发生过的互动；默契值另按“近 30 天互动 40% + 共同经历 30% + 满意反馈 30%”计算，不直接等于积分总数。接口为：

- `GET /api/couple/score`：当前设备的默契值、等级、本月统计和计算分项，需设备 Bearer token。
- `GET /api/couple/score/history`：当前设备积分流水，需设备 Bearer token。
- `POST /api/couple/score/add`：补录纪念日等特殊事件，同时要求管理 Bearer token，普通前端不能自行加分。

数据库升级由 Alembic `20260809_03` 创建 `love_scores` 表，不删除既有订单、评价或游戏数据。完整规则与边界见 [情侣积分系统说明](docs/LOVE_SCORE_SYSTEM.md)。

## V2.3 双人五子棋与游戏记录

“一起玩”新增双人五子棋：创建者生成 6 位房间码，另一台设备输入房间码加入；服务端分配黑白方，黑方先手。棋盘固定为 15×15，所有落子都由后端校验轮次、坐标和占用状态，并由服务端在横、竖和两条斜线方向判断五子连珠。客户端只负责展示棋盘和发送坐标，不直接决定结果。双方都点击“再来一局”后，房间进入下一局。

统一实时入口保持为：

```text
wss://girlfriend-menu-api.onrender.com/ws/game/{room_code}
```

完成一局五子棋后，`game_records` 持久化胜者、时长和结果快照；`game_players` 持久化房间席位和累计局分。情侣积分由后端自动写入：参与双方各 +1，胜者额外 +5，连续第三场获胜额外 +10。用户可在“我们 → 游戏记录”查看自己的历史，管理统计页可查看总局数、五子棋局数、创建者胜率、最常玩的游戏和游戏积分变化。

新增 HTTP 接口：

- `GET /api/games/records/my`：当前设备的游戏记录，需设备 Bearer token。
- `GET /api/admin/games/stats`：游戏统计，需管理 Bearer token。

数据库迁移 `20260809_04` 新增 `game_players`、`game_records` 和 `game_rooms.finished_at`，并把五子棋目录状态调整为可用；旧的大话骰 HTTP/WebSocket 入口继续兼容。协议见 [游戏中心通信协议](docs/GAME_CENTER_PROTOCOL.md)，五子棋规则、状态和持久化边界见 [五子棋系统说明](docs/GOMOKU_SYSTEM.md)。

## V2.4 情侣飞行棋与每日任务

飞行棋复用统一游戏目录和房间表，但采用服务端权威 HTTP 动作接口与 PostgreSQL `game_states` 持久状态。情侣模式下房主创建后自动入座，第二台设备凭 6 位房间码加入；人机模式由服务端立即补齐 AI 席位。每人四颗棋子，掷出 6 才能起飞，公共航线可碰撞，必须精确到达终点。所有骰子点数与 AI 移动都由后端生成，客户端不能提交点数。情侣模式使用不重叠的自适应轮询，页面进入后台后暂停；人机模式不轮询。关闭页面或 Render 进程重启后仍能从数据库恢复棋局。

公共航线和回家跑道设有 LOVE、FOOD、FUN、TASK 事件格。落地时后端从 `game_events` 选择一条启用事件，写入 `game_event_logs`；当前玩家确认完成后获得事件分。同一个事件日志只能结算一次。

“我们 → 每日任务”每天按当前设备生成四项任务：夸奖 +2、完成一顿饭 +5、一起完成一局游戏 +3、五星评价 +3。只有夸奖任务允许手动确认，其余三项必须由订单完成、游戏结算或五星评价在后端自动触发。任务积分以任务 ID 作为唯一来源，重复请求不会重复增加。

迁移 `20260809_05` 新增 `game_states`、`game_events`、`game_event_logs` 和 `daily_tasks`，并把飞行棋目录改为可用；PostgreSQL 使用 JSONB，本地 SQLite 自动使用 JSON。完整规则、API 和状态结构见 [飞行棋与任务系统说明](docs/FLIGHT_TASK_SYSTEM.md)。

## V2.5 斗地主、斗兽棋与游戏 AI

斗地主支持“两位真人 + 一位 AI”和“一位真人 + 两位 AI”：由服务端洗牌并发出 17/17/17 + 3 张底牌；其他玩家只能看到手牌数量。牌型、比较、回合、AI 行动和胜负均由后端判断。斗兽棋提供情侣双人和单人 AI 两种模式，使用标准 7×9 地形与动物等级规则。

## V2.9.1 游戏顺滑与全模式人机

六款对战游戏均提供人机路径：单机大话骰使用本地规则 AI；五子棋、飞行棋、斗地主、斗兽棋和中国象棋使用服务端权威 AI。五子棋支持轻松、规则和挑战三级策略；飞行棋 AI 的骰子与移动由后端生成；斗地主单人模式补齐两个独立 AI 席位。AI 不写入情侣积分、任务或月榜，不会伪装成真实用户。

联机回合制页面改为串行自适应刷新：上一请求完成后才安排下一次，后台暂停，等待房间降低频率，进行中提高频率，相同版本不重复覆盖棋盘。五子棋仍使用 WebSocket，并对本人的落子先做安全的视觉预落子；棋子、骰子和卡牌增加轻量 GPU 友好过渡。详细接口与边界见 [2.9.1 人机模式说明](docs/GAME_AI_MODES_2_9_1.md)。

## V2.9.2 全游戏质量优化

五子棋增加双重威胁识别；飞行棋、斗兽棋和中国象棋开放第三档策略 AI；斗地主补齐连对、飞机和四带二，并提供服务端合法出牌提示；大话骰 AI 改为按二项概率判断叫骰与开骰；转盘增加“连续不重复”和最近结果。设计参考、授权边界和测试范围见 [2.9.2 游戏质量说明](docs/GAME_QUALITY_2_9_2.md)。这些改动已纳入 `2.11.0` 体验版。

## V2.9.3 斗地主横屏牌桌

斗地主大厅和对局改为独立横屏体验：大厅在一屏内完成模式与难度设置，对局采用左右对手、中央出牌区、底部手牌和操作栏的熟悉牌桌层级；保留服务端权威洗牌、发牌、提示、AI 与胜负判断。未复制第三方商标或美术资源。实现与验收边界见 [2.9.3 斗地主横屏说明](docs/LANDLORD_LANDSCAPE_2_9_3.md)。这些改动已纳入 `2.11.0` 体验版。

## V2.10.0 游戏长期稳定化

游戏大厅改为数据驱动的统一卡片，不再在大厅重复承担五子棋建房和加入逻辑；六款长期玩法、人机/双人能力、未完房间和轻量工具有固定层级。飞行棋、斗地主、斗兽棋和中国象棋从“继续游戏”进入时会恢复原房间，并统一显示同步中、在线、离线原因和重试入口；连续失败采用有上限的指数退避，动作增加同步锁，象棋和斗兽棋只在服务器确认后更新棋盘。

实时连接增加指数退避自动重连、抖动和 20 条有界离线队列。大话骰与五子棋快照写入 PostgreSQL `game_states`，Render 进程重启后可恢复棋盘、骰子、轮次和待结算事件；大话骰重连严格按查看者过滤，开盅前只返回本人骰子。实现、参考与剩余边界见 [2.10.0 游戏长期稳定化说明](docs/GAME_LONGEVITY_2_10_0.md)。

## V2.11.0 游戏运行时稳定化

实时房间使用 PostgreSQL 租约确定唯一写入实例，避免多实例同时修改同一棋局；客户端遇到非归属实例会按已有退避机制重新连接。完成结算增加 `pending/complete/failed` 状态和每分钟补偿扫描，进程在奖励、记录或通知阶段异常退出后可以幂等补齐。

等待超过 30 分钟或进行超过 6 小时的房间会标记为 `abandoned`，不会删除历史。飞行棋、斗地主、斗兽棋和中国象棋动作支持 `client_action_id`，同一动作重复到达只返回第一次结果；相同 ID 携带不同内容会被拒绝。斗兽棋和中国象棋增加单回合 5 分钟、三次重复局面、无进展步数及最大步数和棋规则。数据库迁移为 `20260811_10`。完整说明见 [2.11.0 游戏运行时稳定化](docs/GAME_RUNTIME_STABILITY_2_11_0.md)。

两款游戏共用 `game_sessions`。每次动作携带 `expected_version`，另一端先行动时旧请求会收到 409 并刷新，不会覆盖已保存棋局。完成记录继续写入 `game_records` 并自动触发参与、胜利、AI/双人奖励、每日游戏任务和持久成就；斗地主还生成一个可完成的局后情侣约定。

迁移 `20260809_06` 只新增 `game_sessions`、`achievements`、`user_achievements`、`love_tasks` 和索引，并将斗地主、斗兽棋目录切换为可用。完整规则与接口见 [V2.5 游戏与 AI 系统](docs/V25_GAME_AI_SYSTEM.md)。

## V2.6 中国象棋、排行榜与 AI 陪伴

中国象棋复用 V2.5 服务端权威状态和乐观版本锁。情侣模式由两台设备加入红黑席位；AI 模式由服务端生成合法应手。客户端只提交 `a1-i10` 起止坐标，不能直接提交棋盘、结果或 AI 决策。每一步同时写入 `chess_moves`，结束后复用 `game_records`、情侣积分、成就和每日任务结算。

游戏数据中心从完成对局重建 `game_statistics`，月榜范围仅限当前设备参加过的共同房间，并脱敏显示搭档。`game_memories` 记录第一局象棋和近期结果。每日陪伴小结是可解释的本地规则摘要，不调用外部大模型。数据库迁移 `20260809_07` 只新增表、索引与种子数据。完整状态、接口和隐私边界见 [V2.6 中国象棋与游戏数据说明](docs/V26_CHESS_DATA_AI.md)。

## 当前边界

Phase 2C Round 3 已拆分实时边界：订单通知归属
`backend/realtime_events.py`，大话骰/五子棋运行时归属
`backend/game_runtime/manager.py`，`backend/realtime.py` 仅保留旧导入兼容门面。
HTTP/WebSocket 路径、消息字段和关闭码均未改变。

- 普通端使用后端设备会话和 Bearer token；数据库只保存 token 哈希。会话默认 90 天有效，支持轮换和主动撤销。旧 `gf_customer_id` 可通过 `/api/customers/recover` 恢复原身份；恢复时撤销该身份的旧会话，避免丢失历史订单、收藏、积分和游戏记录。
- 邀请码仅发送到后端验证，不再编译进小程序包；它仍是私人应用的设备准入方式，不等同于微信账号登录。
- 所有已开放游戏的进行中权威状态均写入 PostgreSQL；WebSocket 连接对象仍只存在于当前进程，Redis 仅加速热状态。数据库租约保证一个房间同一时刻只有一个写入实例，跨实例切换依靠客户端重连，不承诺不断线迁移。
- 私人部署默认把压缩后的菜品图片持久化到 PostgreSQL；Render 本地 `uploads/` 只允许开发使用。图片量明显增大时再切换 S3-compatible 对象存储。
- 当前没有微信 OpenID、手机号、订阅消息、支付、库存或采购清单。

更完整的当前产品审计见 [项目交接文档](docs/PROJECT_HANDOFF.md)，未来目标架构和分阶段执行提示词见 [V2.0 产品与架构方案](docs/V2_PRODUCT_PLAN.md)。

## V2.8 Release Candidate

V2.8 RC 已完成设备身份、订单归属、12 小时管理令牌、订单状态审计和分页、生产存储抽象、实时重连加固、环境配置集中化及备份恢复工具；当前微信体验版已升级为 `2.11.0`，并加入游戏流畅度、全模式人机与长期稳定化能力。真实能力与未验证边界见 [能力矩阵](docs/CAPABILITY_MATRIX.md)。

小程序三套构建配置位于：

```text
miniprogram/.env.development
miniprogram/.env.staging
miniprogram/.env.production
```

每套至少配置 `TARO_APP_ENV_NAME` 和 `TARO_APP_API_ORIGIN`。WebSocket 地址由 API Origin 自动派生；staging 和生产地址都必须为 HTTPS，缺失时构建直接失败。仓库中的 `.env.staging` 故意不预填地址，只有独立 staging 服务创建并通过隔离核对后才能写入；staging 明确禁止复用生产 API。使用 `npm run build:weapp:staging` 构建真机验收包，生产域名可以通过部署平台或 CI 环境变量覆盖，不要在业务源码重复硬编码。

后端正式环境必须配置：

```text
APP_ENV=production
DATABASE_URL
CUSTOMER_INVITE_CODE
ADMIN_PASSWORD_HASH
ADMIN_INVITE_CODE
ADMIN_SECRET
WECHAT_LOGIN_ENABLED=true
WECHAT_APP_ID
WECHAT_APP_SECRET
ALLOW_LEGACY_CUSTOMER_HEADER=false
CUSTOMER_SESSION_TTL_DAYS=90
UPLOAD_PROVIDER=database
S3_ENDPOINT
S3_REGION
S3_BUCKET
S3_ACCESS_KEY_ID
S3_SECRET_ACCESS_KEY
S3_PUBLIC_BASE_URL
```

私人部署默认使用 `UPLOAD_PROVIDER=database`：后端会先校验并压缩图片，再将少量菜品图片保存到现有 PostgreSQL，通过 `/api/images/{id}` 长缓存访问。这样不需要额外的 R2/S3 账号或密钥。若图片规模增大，可把 `UPLOAD_PROVIDER` 改回 `s3` 并配置上面的 S3/R2 环境变量，现有 `image_url` 不受影响。

`REDIS_URL` 可选；PostgreSQL 是权威状态来源。`GAME_ROOM_LEASE_SECONDS` 默认 30 秒，通常无需修改；`GAME_INSTANCE_ID` 可选，Render 会自动使用实例标识或主机名。正式启动使用 `python serve.py`：它在 Uvicorn 启动前检查 Alembic head，只在需要时迁移；生产应用生命周期本身不自动建表或运行手写 `ALTER TABLE`。

发布前依次执行：

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q

cd ..\miniprogram
cmd /c npm run build:weapp

cd ..
python scripts/check_secrets.py
python scripts/check_release_config.py
```

Windows 下推荐运行 `python run_tests.py -q`；脚本会给每次 pytest 分配仓库内唯一的 `.test-tmp/<uuid>`，避免系统临时目录或上次目录的 ACL/句柄残留导致 fixture 失败。直接运行 `pytest` 仍可用，但遇到权限异常时以该脚本结果为准。

完整步骤见 [V2.8 发布清单](docs/RELEASE_CHECKLIST_V2_8.md)、[备份与恢复](docs/BACKUP_AND_RESTORE.md)和[回滚手册](docs/ROLLBACK_V2_8.md)。正式发布前仍需完成双真机和 Neon 临时库恢复验收。
