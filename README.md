# 情侣智能厨房管家

这是一个面向情侣私厨场景的微信点菜小程序：她负责选菜、提交点菜单和评价，你通过同一个小程序里的管理端查看订单、更新制作状态和维护菜单。

当前产品界面只保留微信小程序。早期 React/Vite 网页端已停用；`frontend/` 仅保留 Render 旧静态服务的停用提示页，不再包含点菜功能。

## 当前版本与线上状态

- 当前开发版本：`2.1.0`
- AppID：`wx08cb090781c3e679`
- 后端：FastAPI，部署于 Render
- 生产数据库：Neon PostgreSQL
- 生产 API：`https://girlfriend-menu-api.onrender.com`
- 2026-08-08 验证结果：API 健康检查正常、数据库为 PostgreSQL、线上有 19 道启用菜品

## 已实现功能

女朋友端：

- 邀请码进入
- “首页、菜单、点菜单、一起玩、我的”五个主导航
- 菜品列表、分类筛选、菜品详情、制作信息和标签
- 点菜清单、数量修改、备注、希望用餐时间、提交订单
- “我的点菜单”、订单状态与历史记录、“再做一次”可编辑草稿
- 按当前设备保存的菜品收藏
- 根据点单、评价、收藏和再次点单计算“她最喜欢”Top 5
- 已完成订单的 1～5 颗爱心评价
- 自定义选项转盘
- 单机 3D 大话骰（原生 WebGL 场景、AI 玩家、上滑开盅）
- 统一游戏大厅、动态游戏目录和“即将上线”状态
- 双人实时大话骰房间、叫骰、开盅与计分板
- 通用 `/ws/game/{room_code}` 房间通信协议

小程序管理端：

- 管理密码登录与退出
- 实时查看订单、备注和希望用餐时间
- 修改订单状态：待接单、已接单、制作中、已完成、暂时做不了
- 新增、编辑、下架菜品
- 维护制作时间、难度、辣度和菜品标签
- 上传菜品图片或手动填写图片链接
- 总订单、已完成订单、最常点菜品、最近订单、平均评分和评价记录统计

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 微信小程序 | Taro 4、React 18、微信原生 Canvas/WebGL |
| 后端 API | Python 3.12、FastAPI、Pydantic 2 |
| 数据访问 | SQLAlchemy 2 |
| 生产数据库 | Neon PostgreSQL |
| 本地数据库 | SQLite（未配置 `DATABASE_URL` 时） |
| 实时通信 | FastAPI WebSocket（管理订单推送、双人骰子房间） |
| 部署 | Render Blueprint + GitHub 自动部署 |
| 自动化 | Pytest、GitHub Actions、微信开发者工具自动化冒烟脚本 |

## 项目结构

```text
girlfriend-menu-app/
├── .github/workflows/ci.yml     # 后端测试与小程序构建
├── backend/                     # FastAPI、SQLAlchemy、实时房间
│   ├── main.py                  # HTTP/WebSocket 路由、鉴权、生命周期
│   ├── crud.py                  # 菜品、订单、评价、统计业务操作
│   ├── database.py              # PostgreSQL/SQLite 连接与兼容升级
│   ├── alembic/                 # 正式数据库迁移版本
│   ├── alembic.ini              # Alembic 配置
│   ├── models.py                # SQLAlchemy 数据模型
│   ├── schemas.py               # API 请求/响应模型
│   ├── realtime.py              # 订单事件与双人骰子房间
│   ├── alembic/versions/        # V2.0 与 V2.1 数据库版本
│   ├── seed.py                  # 19 道测试菜品
│   ├── storage.py               # 本地图片存储
│   └── tests/test_api.py        # 后端集成测试
├── miniprogram/                 # Taro React 微信小程序（主产品）
│   ├── config/                  # Taro 构建配置
│   ├── scripts/smoke-test.cjs   # 微信开发者工具冒烟测试
│   ├── src/api/                 # HTTP 与 WebSocket 客户端
│   ├── src/components/          # 管理端共享导航
│   ├── src/pages/               # 用户端、管理端、转盘、骰子页面
│   ├── src/utils/               # 邀请码、购物车、设备身份、管理令牌
│   ├── project.config.json      # 微信项目配置
│   └── package.json
├── frontend/                    # 旧网页端停用提示，不是当前产品
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
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

本地环境变量示例在 `backend/.env.example`。未配置 `DATABASE_URL` 时会使用 `backend/girlfriend_menu.db`。

启动后检查：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/ready
http://127.0.0.1:8000/docs
```

如果 Windows 对 8000 端口报 `WinError 10013`，可改用 8010：

```bat
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
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
```

2026-08-09 本地验证：后端 `6 passed`、V2.0 → V2.1 迁移在全新 SQLite 数据库执行成功、小程序生产构建成功。

## 数据库

核心表：

- `dishes`：菜品、分类、价格、图片、制作时间、难度、辣度、标签、启用状态
- `orders`：订单状态、备注、希望用餐时间、设备 `customer_id`、再次点单来源
- `order_items`：下单时的菜名和价格快照、数量
- `reviews`：每个订单唯一的一条爱心评价
- `favorite_dishes`：按 `customer_id + dish_id` 唯一保存收藏
- `games`：游戏名称、图标、类型与开放状态
- `game_rooms`：房间码、游戏类型、创建者、房间状态和最大人数

V2.0 使用 Alembic 管理数据库版本。部署启动会先执行迁移，再启动 API；迁移只新增表、字段和索引，不删除或重建旧订单数据。程序内仍保留幂等兼容检查，方便旧的本地 SQLite 直接启动。

完整字段和关系见 `docs/PROJECT_HANDOFF.md`。

## 生产部署

### Render + Neon PostgreSQL

Render 只部署 `backend/`，构建和启动命令已经写在 `render.yaml`：

```text
pip install -r requirements.txt
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

生产环境必须配置：

| 变量 | 用途 |
| --- | --- |
| `DATABASE_URL` | Neon PostgreSQL 连接串 |
| `ADMIN_PASSWORD` | 小程序管理端密码 |
| `ADMIN_INVITE_CODE` | 管理登录和实时骰子房间使用的邀请码 |
| `ADMIN_SECRET` | 生成管理令牌的长随机密钥 |

可选变量：

| 变量 | 用途 |
| --- | --- |
| `FRONTEND_URL` | 未来获准浏览器客户端的 CORS 域名；微信小程序无需配置 |
| `UPLOAD_PROVIDER` | 当前仅支持 `local` |

不要把生产 `.env`、Neon 密码或管理密码提交到 GitHub 或放进项目压缩包。

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
4. 点击“上传”，V2.1 开发版本号使用 `2.1.0`。
5. 微信公众平台进入“版本管理”，把开发版本选为体验版。
6. 体验无误后提交微信审核；审核通过后再正式发布。

## 核心验收流程

1. 清理小程序缓存，输入邀请码，确认首页只突出推荐、常点和今日菜单。
2. 通过底部“菜单”筛选分类，打开详情，收藏一道菜并加入清单。
3. 填写备注和希望用餐时间，提交订单。
4. 从“点菜单”进入历史记录，点击“再做一次”，确认菜品和数量进入可编辑清单，确认后再提交。
5. 进入“我的”查看收藏，并从低强调入口进入“小厨房管理”。
6. 管理端确认新订单实时出现，把状态改为“已完成”。
7. 回到订单详情提交爱心评价，再次进入时只能看到评价结果。
8. 返回首页，确认“她最喜欢”排行已根据当前设备数据更新。
9. 管理端编辑菜品制作时间、难度、辣度和标签，并检查统计与评价记录。
10. 通过“一起玩”测试转盘、单机大话骰以及两台手机的实时对战。

## V2.1 统一游戏中心

游戏大厅通过 `GET /api/games` 获取目录。只有 `status=available` 的游戏可以创建房间；五子棋、飞行棋、斗地主、斗兽棋和中国象棋目前只展示“即将上线”，没有伪造不可用玩法。

新房间通过 `POST /api/games/rooms` 创建，实时连接统一使用：

```text
wss://girlfriend-menu-api.onrender.com/ws/game/{room_code}
```

现有 `/api/games/dice/rooms` 与 `/ws/games/dice/{room_code}` 保留兼容，已经上传的旧小程序不会因后端升级立即失效。协议细节见 [游戏中心通信协议](docs/GAME_CENTER_PROTOCOL.md)。

## 当前边界

- `gf_customer_id` 只保存在微信本地缓存。清缓存后，旧订单不会自动关联回当前设备，但管理端仍能看到。
- 邀请码位于小程序包内，只能作为轻量入口，不是严格安全认证。
- 实时骰子房间保存在单个后端进程内，服务重启后房间会消失。
- Render 本地 `uploads/` 不是持久存储，正式长期使用应接入 Cloudinary、腾讯云 COS、阿里云 OSS 等对象存储。
- 当前没有微信登录、OpenID、手机号、订阅消息、支付、库存或采购清单。

更完整的当前产品审计见 [项目交接文档](docs/PROJECT_HANDOFF.md)，未来目标架构和分阶段执行提示词见 [V2.0 产品与架构方案](docs/V2_PRODUCT_PLAN.md)。
