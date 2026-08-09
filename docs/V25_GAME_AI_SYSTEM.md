# V2.5 斗地主、斗兽棋与 AI 基础架构

## 当前能力

V2.5 在不迁移五子棋 WebSocket 和 V2.4 飞行棋 HTTP 状态的前提下，为新回合制游戏建立可逐步复用的服务端核心：

- `games/core`：纯引擎协议、房间/玩家适配、聊天和版本状态仓库。
- `game_sessions`：每个房间一条 JSONB 权威状态，`version` 用于乐观并发控制。
- `ai/base.py`：`random/rule/strategy` 三档稳定接口；当前实现 random 与 rule。
- `game_records`：继续作为唯一完成对局事实，驱动积分、每日任务和成就。
- `achievements/user_achievements`：定义与用户解锁分离，奖励防重复。
- `love_tasks`：斗地主结束后为两位真人生成一个可完成的情侣约定。

旧游戏保持原协议，避免一次性重构造成线上回归。后续游戏可接入 `GameEngine.apply/serialize/public_state` 和 `GameSessionStore.save`。

## 服务端权威与并发

客户端动作必须携带最近响应中的 `expected_version`。服务端用数据库条件更新：

```text
UPDATE game_sessions
SET state = ..., version = version + 1
WHERE id = ... AND version = expected_version
```

更新不到一行时返回 HTTP 409 与当前版本。客户端应刷新后让用户重新选择，禁止覆盖另一端已经落盘的动作。

斗地主 `public_state(viewer_id)` 只返回当前玩家 `my_hand` 和其他席位的 `hand_counts`；完整 `hands` 永不出现在普通响应。斗兽棋没有隐藏信息，返回完整棋盘。

## 斗地主

- 逻辑席位：真人 A、真人 B、`ai_landlord`。
- 第二位真人加入时，服务端用完整 54 张牌洗牌并发出 17/17/17 + 3 张底牌。
- 叫地主为一轮布尔决策；第一位选择“叫”的玩家成为地主，无人叫时 AI 兜底。
- 支持：单张、对子、三张、三带一、顺子、炸弹、王炸。
- AI 只读取自己的手牌和桌面牌，规则档优先使用最低合法非炸弹牌。
- 任一玩家手牌清空立即结束；AI 获胜可写入统计，但不会获得情侣积分。

接口：

```text
POST /api/games/landlord/create
POST /api/games/landlord/join
POST /api/games/landlord/action
GET  /api/games/{room_code}/state
```

## 斗兽棋

- 标准 7×9 棋盘，红蓝各 8 枚：象、狮、虎、豹、狼、狗、猫、鼠。
- 只有老鼠可进入河流；狮虎可在无老鼠阻挡时跳河。
- 支持陷阱降级、鼠吃象、象不能吃鼠、不能进入己方兽穴。
- 进入对方兽穴、吃光对方棋子或让对方无合法步时获胜。
- `couple` 模式等待第二位真人；`ai` 模式创建后立即对战 `ai_animal`。

接口：

```text
POST /api/games/animal/create
POST /api/games/animal/join
POST /api/games/animal/move
GET  /api/games/{room_code}/state
```

## 积分、成就和情侣约定

- 所有真人完成一局：原有 `GAME_PLAY +1`。
- 真人获胜：原有 `GAME_WIN +5`。
- 简单/规则 AI 对局获胜：`GAME_BONUS +2`；预留高难 AI +8。
- 双人对战获胜：`GAME_BONUS +10`。
- 成就奖励：`ACHIEVEMENT`，以成就定义 ID 防重复。
- 完成斗地主局后约定：`LOVE_TASK +2`。

成就与约定：

```text
GET  /api/games/achievements
GET  /api/games/tasks/my
POST /api/games/tasks/{task_id}/complete
```

## 数据库迁移

Alembic `20260809_06` 新增：

- `game_sessions`
- `achievements`
- `user_achievements`
- `love_tasks`

迁移只新增表和索引，并把 `landlord/jungle` 目录切换为 `available`；不删除 V2.4 及更早数据。已验证全新升级、降级到 `20260809_05`、再升级到 head。

## 验证

```bat
cd /d D:\my-project\girlfriend-menu-app\backend
.venv\Scripts\python.exe -m pytest tests -q

cd /d D:\my-project\girlfriend-menu-app\miniprogram
npm run build:weapp
npm run test:v25
```

测试覆盖 54 张牌唯一性、牌型比较、手牌遮蔽、轮次、AI 行动、斗兽棋河流/兽穴/鼠象规则、房间鉴权、版本冲突、成就幂等和管理统计。
