# 项目交接与首次完整审计

> 当前源码与微信体验版均为 `2.11.1`，日期 2026-08-12。该版本纳入 Phase 2C Round 3 实时边界拆分、生产重连修复与动作延迟优化；正式发布证据仍以公众平台审核与线上健康检查为准。

## 1. 产品定位

项目不是面向餐厅顾客的商业点餐系统，而是一个“情侣私厨协作工具”：

- 女朋友端负责表达“想吃什么、几点吃、有什么备注”和用爱心反馈体验。
- 小厨房管理端负责接单、制作状态、菜单维护和口味复盘。
- 转盘、骰子与五子棋属于情侣互动层，不应打断点菜主流程。

核心产品承诺应保持简单：打开快、选择快、提交可靠、状态看得懂、完成后愿意评价。

## 2. 当前运行事实

| 项目 | 当前状态 |
| --- | --- |
| 小程序技术 | Taro 4 + React 18 |
| 小程序源码版本 | 2.11.1 |
| 微信体验版 | 2.11.1（2026-08-12 上传） |
| 后端 | FastAPI + SQLAlchemy 2 |
| 生产数据库 | Neon PostgreSQL |
| 本地数据库 | SQLite 回退 |
| 生产 API | `https://girlfriend-menu-api.onrender.com` |
| 2026-08-08 健康检查 | `/api/health` 正常；`/api/ready` 返回 PostgreSQL ready |
| 线上启用菜品 | 19 道 |
| 后端自动测试 | 81 项通过（含 2 项 Router 契约测试） |
| 数据库迁移 | Alembic `20260811_11`；空库升级及末级降级/再升级通过 |
| 小程序构建 | `npm run build:weapp` 通过 |
| 正式发布状态 | 代码无法证明；需在微信公众平台“版本管理”确认 |

### V2.8 安全与发布边界

- 普通端由 `/api/customers/session` 建立设备会话，业务接口使用 Bearer token。会话默认 90 天有效，可轮换和撤销；旧 `gf_customer_id` 通过 `/api/customers/recover` 找回原身份和历史数据。
- `CUSTOMER_INVITE_CODE` 只用于普通端准入和身份恢复，不再回退到 `ADMIN_INVITE_CODE`。数据库只保存 token 哈希，恢复成功会撤销该客户的旧会话。
- 管理端令牌为 12 小时 HMAC 签名载荷。修改 `ADMIN_SECRET` 或 `ADMIN_TOKEN_VERSION` 可整体撤销已有令牌。
- 生产启动必须先执行 Alembic；应用内 `create_all` 和旧 SQLite 兼容检查仅在 development/test 运行。
- 私人部署的图片生产存储使用 PostgreSQL provider；`/api/ready` 会校验 provider。图片量增大时可无损切换到 S3-compatible provider。
- 当前自动化验证不覆盖微信双真机、Render 冷启动、Neon 恢复演练或真实对象存储，因此版本保持 RC。
- 以 [V2.8 能力矩阵](CAPABILITY_MATRIX.md)、[发布清单](RELEASE_CHECKLIST_V2_8.md)、[备份恢复](BACKUP_AND_RESTORE.md)和[回滚手册](ROLLBACK_V2_8.md)作为后续交接入口。
- Phase 2A 已将 HTTP/WebSocket 路由拆分到 `backend/api/routes/`，共享鉴权和客户身份依赖位于 `backend/api/dependencies.py`；`main.py` 只保留应用装配，API 和数据库契约未改变。
- Phase 2B 第一轮已将 Dish 与 Favorite 迁移为 `Router -> Service -> Repository`，`crud.py` 暂留兼容 facade；Review、Order、非游戏 Stats 尚未迁移，游戏/实时持久化明确延期到 Phase 2C。

## 3. 系统架构

```mermaid
flowchart LR
  U["女朋友端"] --> MP["Taro React 微信小程序"]
  A["小厨房管理端"] --> MP
  MP -->|"HTTPS JSON"| API["Render / FastAPI"]
  MP <-->|"WSS"| RT["订单推送 / 大话骰 / 五子棋房间"]
  MP -->|"HTTPS 轮询"| FL["持久飞行棋 / 每日任务"]
  MP -->|"HTTPS + version"| GE["斗地主 / 斗兽棋统一游戏核心"]
  API --> DB["Neon PostgreSQL"]
  FL --> DB
  GE --> DB
  API --> FS["Render 本地 uploads（临时）"]
  RT --> DB
  RT --> REDIS["可选 Redis 热缓存"]
  GH["GitHub main"] -->|"自动部署"| API
```

重要边界：

- 用户端与管理端都在同一个微信小程序包里。
- HTTP 数据通过 `miniprogram/src/api/index.js` 访问，订单推送和统一游戏协议分别由对应 WebSocket 客户端封装。
- 订单、菜品、评价、游戏玩家、完成对局、飞行棋状态、V2.5 版本棋局、互动、任务、成就、情侣积分和统计持久化到 PostgreSQL。
- 实时连接对象保留在进程内存；大话骰和五子棋权威快照写入 PostgreSQL `game_states`，Redis 只做可选热缓存。单实例进程重启后可恢复进行中棋盘、骰子与轮次。
- 旧 React/Vite 网页端已退休且源码已清理，不再作为构建、部署或功能入口。

## 4. 页面地图

| 页面 | 路径 | 作用 |
| --- | --- | --- |
| 首页/邀请码 | `pages/index/index` | 邀请码、智能推荐、最近常点、Top 5、今日菜单 |
| 菜单 | `pages/menu/index` | 搜索、分类、收藏、加入清单 |
| 一起玩 | `pages/games/index` | 统一游戏目录、未完房间恢复、人机/双人能力与轻量工具入口 |
| 我们 | `pages/couple/index` | 默契值、本月互动、共同成长、口味收藏和低强调管理入口 |
| 积分明细 | `pages/couple/score` | 按日期查看积分来源 |
| 共同记录 | `pages/couple/records` | 第一次点餐、完成次数、游戏次数和最爱菜品 |
| 游戏记录 | `pages/couple/game-records` | 当前设备的五子棋局数、胜局、时长和最近结果 |
| 成就 | `pages/couple/achievements` | 根据已有业务数据派生的成长成就 |
| 菜品详情 | `pages/detail/index` | 菜品信息与加入清单 |
| 点菜清单 | `pages/cart/index` | 数量、备注、时间、提交订单 |
| 我的点菜单 | `pages/my-orders/index` | 当前设备的历史订单 |
| 订单详情 | `pages/order-detail/index` | 状态、明细、爱心评价 |
| 自定义转盘 | `pages/wheel/index` | 2～12 个本地选项的随机转盘 |
| 单机大话骰 | `pages/dice/index` | 原生 WebGL 骰子、AI 对局 |
| 双人大话骰 | `pages/dice-online/index` | 房间、实时叫骰、开盅、计分 |
| 双人五子棋 | `pages/games/gomoku/index` | 15×15 实时棋盘、轮次、结算和再来一局 |
| 情侣飞行棋 | `pages/games/flight/index` | 服务端骰子、四棋子、互动事件和持久棋局 |
| 情侣斗地主 | `pages/games/landlord/index` | 两位真人 + AI、私有手牌、服务端牌型和结算 |
| 情侣斗兽棋 | `pages/games/animal/index` | 7×9 棋盘、双人房间或单人 AI |
| 每日任务 | `pages/couple/tasks` | 今日进度、自动触发任务和最近互动 |
| 我们的故事 | `pages/couple/timeline` | 共同时间轴、手写记录和纪念日提醒 |
| 消息 | `pages/notifications/index` | 订单进度、游戏与纪念日消息 |
| 管理登录 | `pages/admin-login/index` | 管理密码登录 |
| 管理总览 | `pages/admin-dashboard/index` | 订单、菜品、统计入口 |
| 管理订单 | `pages/admin-orders/index` | 全部订单、实时刷新、改状态 |
| 菜品管理 | `pages/admin-dishes/index` | 新增、编辑、下架、图片上传 |
| 管理统计 | `pages/admin-stats/index` | 订单、排行、评分、评价记录和游戏统计 |

## 5. 本地状态与身份

| key | 内容 | 清缓存影响 |
| --- | --- | --- |
| `gf_invite_passed` | 是否通过邀请码 | 需要重新输入邀请码 |
| `gf_customer_id` | 当前设备的匿名客户标识 | “我的点菜单”无法自动找回旧订单 |
| `gf_authenticated_customer_id` | 后端确认后的稳定客户标识 | 需要用原 `gf_customer_id` 和邀请码重新恢复 |
| `gf_customer_token` | 设备会话 Bearer 原始令牌 | 需要重新输入邀请码恢复会话 |
| `gf_customer_expires_at` | 当前设备会话过期时间 | 过期后自动清除已认证状态并进入恢复流程 |
| `gf_menu_cart` | 未提交的点菜清单 | 清单丢失 |
| `gf_repeat_order_draft` | 再次点单的来源和备注 | 草稿来源信息丢失 |
| `gf_admin_token` | 管理登录令牌 | 需要重新登录管理端 |
| `gf_wheel_items` | 自定义转盘选项 | 转盘恢复默认值 |
| `gf_game_reconnect_{ROOM}` | 单房间重连原始令牌 | 仍能从“继续游戏”发现房间，但需重新签发令牌 |

`customer_id` 不是微信账号，也不是 OpenID。它只解决最小版本里“同一台设备再次打开还能找到订单”的需求。

V2.7 的 `users.user_code` 对旧 `customer_id` 做兼容映射，不改变现有 key。只要设备仍保留原 `gf_customer_id`，会话过期或 token 丢失后可凭普通端邀请码恢复原身份；如果把微信小程序全部本地存储一并清空，则无法仅凭邀请码推断原身份。本版本没有冒充微信账号、手机号或 OpenID，也不是完整账号找回系统。

## 6. 数据模型

### dishes

| 字段 | 类型/约束 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 菜品编号 |
| `name` | String(100), required | 菜名 |
| `description` | Text | 描述 |
| `category` | String(50), indexed | 分类 |
| `price` | Float | 展示价格 |
| `image_url` | String(500) | 网络图片或 `/uploads/...` |
| `cook_time` | Integer, nullable | 制作时间（分钟） |
| `difficulty` | Integer, nullable | 难度 1～5 |
| `spicy_level` | Integer, nullable | 辣度 0～3 |
| `tags` | JSON, nullable | 最多 10 个展示标签 |
| `is_active` | Boolean, indexed | 软下架标记 |
| `created_at` | DateTime | 创建时间 |

### orders

| 字段 | 类型/约束 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 订单编号 |
| `status` | String(20), indexed | 五种订单状态之一 |
| `note` | Text | 备注 |
| `desired_time` | String(50) | 希望用餐时间，当前不是结构化时间 |
| `customer_id` | String(100), nullable, indexed | 设备匿名标识，兼容无标识旧订单 |
| `source_order_id` | FK orders, nullable, indexed | “再做一次”的来源订单 |
| `created_at` | DateTime, indexed | 提交时间 |

### order_items

| 字段 | 类型/约束 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 明细编号 |
| `order_id` | FK orders, indexed | 所属订单 |
| `dish_id` | FK dishes | 原菜品编号 |
| `dish_name` | String(100) | 下单时菜名快照 |
| `price` | Float | 下单时价格快照 |
| `quantity` | Integer | 数量 |

### reviews

| 字段 | 类型/约束 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 评价编号 |
| `order_id` | FK orders, unique | 一个订单只能评价一次 |
| `rating` | Integer | 1～5 颗爱心 |
| `want_again` | String(20) | 想吃 / 一般 / 暂时不想 |
| `comment` | Text | 可选建议 |
| `created_at` | DateTime | 评价时间 |

### favorite_dishes

| 字段 | 类型/约束 | 说明 |
| --- | --- | --- |
| `id` | Integer PK | 收藏编号 |
| `customer_id` | String(100), indexed | 当前设备匿名标识 |
| `dish_id` | FK dishes, indexed | 收藏菜品 |
| `created_at` | DateTime | 收藏时间 |

`customer_id + dish_id` 唯一，同一设备不会重复收藏。

### customers / customer_sessions

- `customers` 以唯一 `customer_id` 保存稳定客户档案；原 `token_hash` 字段暂时保留，用于旧会话平滑迁移。
- `customer_sessions` 保存客户外键、唯一 token 哈希、创建/最后访问/过期/撤销时间、轮换来源和可选设备标签；任何接口都不会返回数据库中的哈希。
- 新 token 默认 90 天有效，`CUSTOMER_SESSION_TTL_DAYS` 可限制在 1～365 天。刷新会撤销旧 token 并记录轮换链；主动撤销后旧 token 立即失效。
- Alembic `20260811_11` 只新增会话表，并把旧 `customers.token_hash` 回填为 90 天迁移会话；不会删除客户、订单、收藏、积分或游戏记录，降级仅移除新会话表。

### games / game_rooms / game_players / game_records

- `games`：游戏名称、文字图标、唯一 `type`、`available/coming_soon/maintenance` 状态；当前大话骰、五子棋、飞行棋、斗地主、斗兽棋与中国象棋可用。
- `game_rooms`：唯一房间码、游戏类型、创建者、`waiting/playing/finished` 状态、最大人数、创建时间和可空完成时间 `finished_at`。
- `game_players`：所属房间、设备 `player_id`、席位、房间累计局分和加入时间；`room_id + player_id`、`room_id + seat` 分别唯一。
- `game_records`：所属房间、局号、游戏类型、胜者、时长、结果 JSON 和完成时间；`room_id + round_number` 唯一，避免重试重复结算。
- 房间元数据、玩家、已完成记录持久化；大话骰状态与进行中的五子棋棋盘仍在单进程内存中。

### love_scores

- 记录 `customer_id`、正积分、固定行为类型、描述、关联业务编号和发生时间。
- `customer_id + type + related_id` 唯一，使订单完成、五星评价和再次点单的自动奖励保持幂等。
- 当前自动规则：订单完成 +10、五星评价 +5、通过“再做一次”提交新订单 +2；五子棋参与双方各 +1、胜者额外 +5、连续第三场获胜再 +10。
- 默契值按近 30 天互动、共同经历与满意反馈加权计算，不直接等于累计积分。

关系：订单拥有多个明细和最多一条评价。情侣积分通过 `related_id` 保留业务来源但不建立强外键，以兼容订单、游戏和特殊事件。菜品下架采用 `is_active = false`，不会破坏历史订单快照。

V2.3 使用 Alembic `20260809_04` 追加 `game_players`、`game_records` 与 `game_rooms.finished_at`，并把五子棋目录状态改为 `available`。迁移不会删除或重建旧房间、订单、评价或情侣积分数据；全新 SQLite 已验证升级、降级和再次升级。

## 7. API 清单

公共 HTTP：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 服务存活检查 |
| GET | `/api/ready` | 数据库就绪检查 |
| POST | `/api/customers/session` | 使用普通端邀请码新建设备会话 |
| POST | `/api/customers/claim-legacy` | 兼容旧客户端的一次性认领接口；重复认领仍返回 409 |
| POST | `/api/customers/recover` | 使用原 `customer_id` 和普通端邀请码恢复身份，并轮换该客户的旧会话 |
| POST | `/api/customers/refresh` | 使用当前 Bearer 轮换为新会话 |
| POST | `/api/customers/revoke` | 主动撤销当前设备会话 |
| GET | `/api/dishes` | 菜品列表/分类筛选 |
| GET | `/api/dishes/{id}` | 菜品详情 |
| GET | `/api/games` | 游戏大厅目录与开放状态 |
| POST | `/api/games/rooms` | 为开放游戏创建统一房间 |
| GET | `/api/games/rooms/{room_code}` | 查询房间元数据、玩家席位和状态 |
| GET | `/api/games/records/my` | 当前设备的历史游戏记录（设备 Bearer） |
| GET | `/api/favorites` | 当前设备收藏（设备 Bearer） |
| POST | `/api/favorites/{dish_id}` | 收藏菜品（设备 Bearer） |
| DELETE | `/api/favorites/{dish_id}` | 取消收藏（设备 Bearer） |
| POST | `/api/orders` | 提交订单 |
| POST | `/api/orders/{id}/repeat-preview` | 返回可编辑的再次点单草稿（设备 Bearer） |
| GET | `/api/orders/me` | 当前设备历史订单（设备 Bearer） |
| GET | `/api/orders/{id}` | 订单详情 |
| POST | `/api/orders/{id}/review` | 提交评价 |
| GET | `/api/orders/{id}/review` | 查询评价 |
| GET | `/api/stats/favorite-ranking` | 当前设备喜欢排行（设备 Bearer） |
| GET | `/api/couple/score` | 默契值、本月统计和计算分项（设备 Bearer） |
| GET | `/api/couple/score/history` | 当前设备积分流水（设备 Bearer） |
| POST | `/api/games/dice/rooms` | 创建双人骰子房间（校验邀请码） |

管理 HTTP（Bearer token）：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/admin/login` | 密码 + 邀请码换取令牌 |
| POST | `/api/upload/image` | 上传最多 5MB 的 jpg/jpeg/png/webp |
| POST | `/api/dishes` | 新增菜品 |
| PUT | `/api/dishes/{id}` | 编辑菜品 |
| DELETE | `/api/dishes/{id}` | 软下架菜品 |
| GET | `/api/orders` | 全部订单 |
| PATCH | `/api/orders/{id}/status` | 修改订单状态 |
| GET | `/api/stats/summary` | 总订单、已完成、最近下单时间 |
| GET | `/api/stats/dishes` | 每道菜点单次数和最近时间 |
| GET | `/api/stats/recent` | 最近 10 个订单 |
| GET | `/api/admin/games/stats` | 总局数、五子棋局数、胜率、最常玩游戏和游戏积分变化 |
| POST | `/api/couple/score/add` | 为指定设备补录积分（管理 Bearer） |

WebSocket：

| 路径 | 用途 |
| --- | --- |
| `/ws/admin/orders` | 管理端新订单、状态和评价事件 |
| `/ws/games/dice/{room_code}` | 双人骰子房间状态同步 |
| `/ws/game/{room_code}` | 统一游戏房间协议（大话骰与服务端权威五子棋） |

## 8. 关键业务状态

订单状态固定为：

```text
待接单 → 已接单 → 制作中 → 已完成
                   ↘ 暂时做不了
```

当前后端只校验状态值，不限制状态跳转顺序；管理端可以从任意状态切到任意合法状态。

评价规则：

- 只有“已完成”订单可以评价。
- 数据库唯一约束和业务检查共同防止重复评价。
- 当前公共评价接口没有验证评价人是否拥有该订单。

双人骰子状态：

```text
waiting → rolling → bidding → finished → rematch/rolling
```

每个房间固定两人，每人 5 颗骰子；叫非 1 点时，1 作为万能点。房间元数据入库，但骰子点数、当前叫法和局分只存在后端内存中，大话骰暂不写 `game_records` 或情侣积分。

双人五子棋状态：

```text
waiting → playing → finished → 双方 rematch/playing
```

棋盘固定 15×15，第一席黑方先手。落子轮次、坐标、占位和横/竖/两斜线五连均由服务端权威判断；客户端不提交胜负。已完成记录、玩家席位和积分持久化，正在进行的棋盘仍是进程内存态。

## 9. 当前优势

1. 点菜主链路完整：浏览、清单、提交、状态、历史、评价已经闭环。
2. 管理端内置小程序，个人主体无法配置 web-view 业务域名时仍可使用。
3. 菜品软下架和订单快照保护历史数据。
4. SQLite 与 PostgreSQL 双环境可运行，旧库补字段是幂等的。
5. 生产环境变量没有提交到仓库。
6. 已有 CI、后端集成测试和微信开发者工具冒烟脚本。
7. 网络错误、Render 冷启动、图片失败和页面渲染异常都有基础回退提示。

## 10. 风险与技术债

### P0：正式发布前外部验收

1. PostgreSQL 图片 provider 仍需完成一次生产上传、读取验收。
2. 所有双人游戏仍需两台真机完成加入、弱网、切后台、断线恢复和重开验收。

### P1：稳定性与维护

1. V2.11 已用 PostgreSQL 租约解决多实例同时写入同一实时房间；连接对象仍在实例内，实例切换会经历一次客户端重连，不是无感迁移。
2. V2.11 已增加每分钟结算补偿、房间 TTL/`abandoned`、REST 动作幂等和象棋/斗兽棋超时和棋；仍需在真实 Render 多实例与双真机上做故障注入验收。
3. `failed` 结算自动重试上限为 10 次；持续失败目前通过数据库字段和日志排查，管理端尚无专门的失败结算工作台。
4. 生产图片必须使用 PostgreSQL 或 S3-compatible 持久化 provider；Render 本地目录仅供开发。

### P2：体验与产品结构

1. 游戏大厅已经收敛为固定六款长期玩法；后续新增游戏必须先满足统一恢复、错误反馈、规则测试和双真机验收，不再直接堆入口。
2. 已有五项底部主导航；非 Tab 页面仍混用 `navigateTo/redirectTo/reLaunch`，需继续统一返回策略。
3. 分类、历史和统计缺少搜索、分页和筛选。
4. 价格在私厨场景是否有价值尚未验证，可考虑改成“难度/准备时间/辣度”。
5. `desired_time` 是自由文本，无法可靠排序或做提醒。
6. 游戏视觉主题仍不完全统一，后续只在共享状态和触控规范稳定后继续打磨单个棋盘。

## 11. UI/UX 方向

建议保留“温馨、克制、私厨”的品牌，不继续堆叠更多粉色渐变。

信息架构建议：

- 首页第一屏只放“今天想吃什么”、最近常点和分类。
- 主导航固定为“首页 / 菜单 / 点菜单 / 一起玩 / 我们”。
- 转盘和两种骰子统一收进“一起玩”，避免挤压点菜主任务。
- 管理入口位于“我们”底部，用低强调入口进入密码页。
- 订单状态用统一时间线，不只显示一句状态文案。
- 菜品卡片增加“最近点过”“她喜欢”“制作时间”等更贴合私厨的信号。

视觉规则建议：

- 正文字号不低于 24rpx，次要文字不低于 22rpx。
- 所有点击区域最小高度 88rpx。
- 主色只用于关键动作和状态，不同时在每张卡片上使用。
- 统一圆角层级：按钮 24rpx、卡片 28rpx、大容器 36rpx。
- 深色骰子游戏允许成为独立视觉主题，但返回点菜区后恢复统一浅色系统。
- 对比度、动态字体、长菜名、网络慢和无图片状态必须纳入真机验收。

## 12. 建议路线图

### 1.0.20：安全与可靠性修复

- 为订单创建不可枚举访问凭证，历史与评价接口校验凭证或设备身份。
- API 地址按开发/生产构建环境管理。
- 图片规模增长后迁移到对象存储。
- 实时房间增加 TTL、断线重连提示和服务重启提示。
- 增加订单状态转换测试、图片验证测试和权限测试。

### 1.1：点菜体验升级

- 重做首页信息层级与底部导航。
- 最近常点、收藏、再次点单。
- 辣度、忌口、预计制作时间。
- 希望用餐时间改为日期时间选择器。
- 订单状态时间线与状态更新时间。

### 1.2：小厨房协作

- 根据订单自动生成采购清单。
- 菜品可用/今日售罄开关。
- 微信订阅消息：新订单、已接单、可以开吃。
- 管理端分页、筛选、导出和数据库正式迁移。

### 2.0：智能私厨（需验证需求后再做）

- 基于历史、评分、忌口和天气做规则推荐。
- 心情选择与轻量推荐。
- 月度口味报告和共同回忆，不优先做复杂餐厅 ERP。

## 13. 下一位开发者的工作原则

1. 不破坏点菜、历史、评价和管理端主链路。
2. 修改 API 时同时更新 Pydantic schema、前端调用、测试和本文档。
3. 新功能先确认属于“点菜主流程”“小厨房管理”还是“情侣互动”，不要继续堆在首页。
4. 不在仓库、截图、日志或压缩包中放生产数据库密码、管理密码和密钥。
5. 每次发布至少通过后端测试、小程序生产构建和真机核心验收。

## 14. 截图采集清单

为了让产品、UI 或下一位 AI 看到真实体验，建议从同一台真机、同一版本采集：

用户端：

1. 邀请码页
2. 菜单首页与分类
3. 菜品详情
4. 点菜清单
5. 我的点菜单
6. 订单详情与评价
7. 转盘
8. 单机骰子开盅前/后
9. 双人大话骰房间与计分板
10. 双人五子棋等待、对局、结算与再来一局
11. 情侣飞行棋等待、双人移动、随机事件和结算
12. 每日任务进度、手动夸奖与自动任务
13. “我们的游戏记录”页面

管理端：

1. 管理登录
2. 管理总览
3. 实时订单
4. 菜品管理
5. 点菜与游戏统计

截图中不要出现生产密码、Neon 连接串或管理 token。
