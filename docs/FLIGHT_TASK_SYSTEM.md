# V2.4 情侣飞行棋与每日任务系统

## 1. 范围与设计边界

V2.4 在不改变点菜、订单、评价、管理登录、大话骰和五子棋协议的前提下增加：

- 双人情侣飞行棋；
- 持久化游戏状态；
- 随机情侣互动事件；
- 每日任务及后端自动结算；
- 管理端情侣互动统计。

飞行棋使用现有目录类型 `aeroplane`，用户界面和 API 使用“flight/飞行棋”。这样保留 V2.1 已有游戏目录数据，不产生两个表示同一游戏的类型。

## 2. 数据库迁移

Alembic `20260809_05` 只新增表、索引和目录状态，不删除旧数据：

| 表 | 用途 |
| --- | --- |
| `game_states` | 每个房间一份权威棋局快照；PostgreSQL 为 JSONB，SQLite 为 JSON |
| `game_events` | LOVE、FOOD、FUN、TASK 可用事件目录 |
| `game_event_logs` | 某一房间、玩家实际触发和完成的事件 |
| `daily_tasks` | 当前设备每天四项任务及结算状态 |

`game_states.room_id` 唯一；`daily_tasks` 对 `customer_id + date + type` 唯一。已有 `game_records` 继续保存已完成对局，`love_scores` 继续保存只追加积分流水。

## 3. 飞行棋规则

- 房间固定两名玩家，每人四颗棋子；第一席红色，第二席蓝色。
- 棋子位置 `-1` 为机库，`0～27` 为公共航线，`28～31` 为回家跑道，`32` 为到达。
- 只有掷出 6 才能从机库起飞；起飞后掷几点走几格。
- 超过终点的点数不能移动，必须精确到达 32。
- 公共航线落在对方棋子所在格时，将对方棋子送回机库。
- 掷出 6 并完成移动/互动后保留回合；无棋子可移动时自动换人。
- 四颗棋子全部到达后结束，胜负只由服务端判断。

状态机：

```text
waiting -> playing -> finished
             |
             +-- ROLL_DICE -> MOVE_PIECE -> 可选 COMPLETE_EVENT
```

骰子使用后端 `secrets.randbelow(6) + 1`，客户端的动作请求没有 dice 字段。

## 4. 状态结构

`game_states.state` 是 JSON 安全快照：

```json
{
  "version": 1,
  "phase": "playing",
  "round": 1,
  "players": [
    {"id": "gf_xxx", "name": "男朋友", "seat": 1, "color": "red"}
  ],
  "pieces": {"gf_xxx": [-1, 0, 12, 32]},
  "turn_id": "gf_xxx",
  "dice": null,
  "movable": [],
  "winner_id": null,
  "last_action": null,
  "pending_event": null,
  "started_at": "2026-08-09T20:00:00",
  "event_sequence": 0
}
```

客户端只能依据 `movable` 高亮棋子，不应自行推导并提交目标位置。每次动作后服务端写回完整状态；页面使用约 2.2 秒轮询，因此关闭页面后重新进入可以恢复。

## 5. 飞行棋 API

所有接口都要求当前设备的 `X-Customer-Id`。创建和加入同时校验小程序邀请码。

| 方法 | 路径 | 请求 |
| --- | --- | --- |
| POST | `/api/games/flight/create` | `player_name`, `invite_code` |
| POST | `/api/games/flight/join` | `room_code`, `player_name`, `invite_code` |
| GET | `/api/games/flight/{room_code}/state` | 无 body |
| POST | `/api/games/flight/action` | `room_code`, `action`, 可选 `piece_index` |

动作固定为：

- `ROLL_DICE`：后端生成 1～6；
- `MOVE_PIECE`：`piece_index` 必须为 0～3 且在服务端 `movable` 内；
- `COMPLETE_EVENT`：只允许触发该事件的当前玩家确认。

陌生设备查询房间返回 403；抢回合、重复掷骰、移动不可用棋子、跳过待完成事件均返回 409。

## 6. 随机互动事件

固定类型：

| 类型 | 示例 |
| --- | --- |
| `LOVE` | 夸对方三个优点 |
| `FOOD` | 一起决定明天最想吃的一道菜 |
| `FUN` | 一起哼十秒最喜欢的歌 |
| `TASK` | 给对方一个二十秒拥抱 |

落在事件格时，服务端从同类型且 `enabled=true` 的目录中选择事件，立即创建 `pending` 日志。确认完成后日志改为 `completed`，以日志 ID 写入 `GAME_EVENT` 积分。重复确认不会再次加分。

## 7. 每日任务

每天按 UTC+8 日期为当前设备幂等生成：

| 类型 | 任务 | 奖励 | 触发来源 |
| --- | --- | ---: | --- |
| `COMPLIMENT` | 给对方一句真诚的夸奖 | +2 | 用户手动确认 |
| `MEAL` | 一起完成一顿饭 | +5 | 管理端首次把订单设为已完成 |
| `GAME` | 一起完成一局小游戏 | +3 | 五子棋/飞行棋服务端结算 |
| `REVIEW` | 记录一次五星用餐感受 | +3 | 五星评价提交成功 |

API：

```http
GET /api/couple/tasks/today
X-Customer-Id: gf_xxx
```

```http
POST /api/couple/tasks/{task_id}/complete
X-Customer-Id: gf_xxx
```

完成接口仅允许 `COMPLIMENT`。其余任务若由客户端手动调用会返回 409。奖励类型为 `DAILY_TASK`，`related_id` 为任务 ID。

## 8. 游戏与积分结算

飞行棋完成时：

1. 以 `room_id + round_number` 幂等写入 `game_records`；
2. 双方各获得 `GAME_PLAY +1`；
3. 胜者获得 `GAME_WIN +5`；
4. 当天首次游戏为双方完成 `GAME +3` 每日任务；
5. 连续第三局胜利沿用统一游戏奖励，获得 `SPECIAL_EVENT +10`。

记录在所有奖励完成前标记 `_settlement=pending`，游戏历史接口不返回仍在结算的记录；结算完成后改为 `complete`，避免客户端先看到对局却暂时看不到积分。

## 9. 前端页面与管理统计

- `pages/games/index`：飞行棋开放卡片；
- `pages/games/flight/index`：创建/加入、棋盘、服务器骰子、事件弹窗和结算；
- `pages/couple/tasks`：进度、四项任务、最近随机互动；
- `pages/couple/index`：今日任务快捷卡；
- `pages/admin-stats/index`：飞行棋局数、互动次数、任务完成数和近 7 天增长。

管理接口 `/api/admin/games/stats` 新增：`flight_games`、`interaction_count`、`completed_tasks`、`love_score_growth`。

## 10. 验证

V2.4 本地验证基线：

- 后端 `24 passed`；
- Alembic 全新升级、降级至 `20260809_04`、再升级到 `20260809_05` 成功；
- `npm run build:weapp` 生产构建成功；
- `git diff --check` 必须通过。

体验版仍需两台真机验证：创建/加入、等待同步、服务端骰子、事件确认、关闭重进、四棋子到达、积分和管理统计。
