# V2.7 游戏中心通信协议

## 目标与边界

游戏大厅、房间元数据、大话骰和双人五子棋继续共用实时通信入口。飞行棋继续使用 V2.4 HTTP 状态；V2.5 斗地主与斗兽棋使用统一 `game_sessions + version` HTTP 协议，不改变旧 WebSocket。

持久化边界：

- `games` 保存游戏目录和开放状态；当前 `dice`、`gomoku`、`aeroplane`、`landlord`、`jungle`、`chinese_chess` 为 `available`。
- `game_rooms` 保存房间码、类型、创建者、人数、生命周期状态和完成时间。
- `game_players` 保存玩家设备标识、席位、房间局分和加入时间。
- `game_records` 保存每个房间每一局的胜者、时长和服务端结果快照。
- `love_scores` 保存五子棋参与、获胜和三连胜积分。
- `game_states` 保存飞行棋权威 JSONB 快照，`game_events/game_event_logs` 保存互动目录与实际记录。
- `game_sessions` 保存 V2.5 游戏 JSONB、当前回合和乐观锁版本；成就与牌局约定分别持久化。
- WebSocket 连接对象仍是单进程内存状态；棋盘、骰子、轮次可镜像到 Redis 热快照，重新连接后恢复。未配置 Redis 时自动退回单进程状态，持久房间和记录仍在 PostgreSQL。
- `game_reconnect_tokens` 只保存重连令牌哈希，`game_replays` 保存完成对局的通用步骤与最终状态。

## HTTP API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/games` | 返回全部游戏及 `available/coming_soon/maintenance` 状态 |
| POST | `/api/games/rooms` | 为已开放游戏创建房间 |
| GET | `/api/games/rooms/{room_code}` | 查询房间元数据、玩家席位和状态 |
| GET | `/api/games/records/my` | 查询当前设备最近游戏记录，需 `X-Customer-Id` |
| GET | `/api/admin/games/stats` | 管理端游戏统计，需 Bearer token |
| POST | `/api/games/flight/create` | 创建飞行棋并让当前设备入座 |
| POST | `/api/games/flight/join` | 按房间码加入飞行棋 |
| GET | `/api/games/flight/{room_code}/state` | 获取持久飞行棋状态 |
| POST | `/api/games/flight/action` | 掷骰、移动或确认互动 |
| POST | `/api/games/landlord/create` | 创建两位真人 + AI 斗地主房间 |
| POST | `/api/games/landlord/join` | 第二位真人加入并由服务端发牌 |
| POST | `/api/games/landlord/action` | 叫地主、出牌、不出或聊天 |
| POST | `/api/games/animal/create` | 创建情侣或 AI 斗兽棋 |
| POST | `/api/games/animal/join` | 加入情侣斗兽棋 |
| POST | `/api/games/animal/move` | 行棋、认输或聊天 |
| GET | `/api/games/{room_code}/state` | 获取 V2.5 当前用户视图与版本 |
| POST | `/api/games/chess/create` | 创建情侣房间或 AI 象棋训练局 |
| POST | `/api/games/chess/join` | 加入象棋黑方席位 |
| POST | `/api/games/chess/move` | 服务端校验落子、认输或聊天 |
| GET | `/api/games/chess/{room_code}/state` | 获取持久象棋棋局与版本 |
| GET | `/api/games/chess/{game_id}/history` | 原房间成员查看落库棋谱 |
| GET | `/api/games/ranking` | 私人战绩与共同房间脱敏月榜 |
| GET | `/api/games/memories/my` | 当前设备的游戏记忆 |
| GET | `/api/games/ai/players` | AI 角色与透明难度目录 |
| GET | `/api/games/ai/summary` | 基于真实记录的规则日报 |

创建五子棋房间示例：

```json
{
  "game_type": "gomoku",
  "creator": "gf_device_id",
  "invite_code": "邀请口令"
}
```

房间状态只使用 `waiting`、`playing`、`finished`。房间码由后端生成，为去掉易混字符的 6 位大写字母或数字。

### 飞行棋 HTTP 动作

飞行棋内部目录类型仍为 `aeroplane`，公开路由使用更直观的 `flight`。所有请求都带 `X-Customer-Id`；创建/加入还带邀请码。动作请求示例：

```json
{"room_code":"ABC234","action":"ROLL_DICE"}
```

```json
{"room_code":"ABC234","action":"MOVE_PIECE","piece_index":2}
```

```json
{"room_code":"ABC234","action":"COMPLETE_EVENT"}
```

客户端不能传骰子点数或目标坐标。服务端生成点数、计算 `movable`、移动和碰撞，并返回完整状态。进行中的飞行棋写入 `game_states`，页面重新打开或服务进程重启后可以恢复。完整字段见 [飞行棋与任务系统](FLIGHT_TASK_SYSTEM.md)。

## 统一 WebSocket

连接入口：

```text
/ws/game/{room_code}
```

连接成功后必须在 10 秒内先发送 `join`。所有 V2 客户端消息使用同一信封：

```json
{
  "type": "action_name",
  "game": "game_type",
  "data": {}
}
```

服务端对 `type` 和 `game` 做小写归一化；客户端仍应统一发送小写值。

加入五子棋房间：

```json
{
  "type": "join",
  "game": "gomoku",
  "data": {
    "player_id": "gf_device_id",
    "name": "我",
    "invite_code": "邀请口令"
  }
}
```

服务端按照持久席位分配颜色：第一席黑棋、第二席白棋。相同 `player_id` 重连时复用原席位；第三个不同设备不能加入已经满员的房间。

### 五子棋操作

落子：

```json
{
  "type": "move",
  "game": "gomoku",
  "data": {"x": 7, "y": 8}
}
```

坐标范围为 `0`～`14`。服务端验证房间状态、当前回合、坐标类型、坐标范围和格点占用，并在横、竖、左斜、右斜四个方向判断是否达到五连。客户端只发送坐标，不提交胜负结果。

再来一局：

```json
{"type":"rematch","game":"gomoku","data":{}}
```

只有本局结束后可以申请；双方都申请后清空棋盘并进入下一局，黑方仍先手。

五子棋状态示例（`board` 为节省篇幅只展示了数组形状片段，真实响应固定为 15×15）：

```json
{
  "type": "state",
  "game": "gomoku",
  "room_code": "ABC234",
  "data": {
    "size": 15,
    "board": [[0, 0, 0]],
    "players": [
      {
        "id": "gf_device_id",
        "name": "我",
        "seat": 1,
        "color": "black",
        "connected": true,
        "rematch_ready": false,
        "score": 0
      }
    ],
    "phase": "playing",
    "turn_id": "gf_device_id",
    "winner_id": null,
    "winner_color": null,
    "last_move": {"x": 7, "y": 8, "player_id": "gf_device_id", "color": "black"},
    "move_count": 1,
    "is_draw": false,
    "round": 1,
    "outcome": null
  }
}
```

`board[y][x]` 中 `0` 表示空位、`1` 表示黑棋、`2` 表示白棋。`phase` 使用 `waiting`、`playing`、`finished`；结束时 `outcome` 会包含胜者、和局标识及情侣互动奖励文案。

### 大话骰操作

```json
{"type":"roll","game":"dice","data":{"values":[1,2,3,4,5]}}
{"type":"bid","game":"dice","data":{"quantity":3,"face":5}}
{"type":"challenge","game":"dice","data":{}}
{"type":"rematch","game":"dice","data":{}}
```

大话骰继续使用原有 `waiting → rolling → bidding → finished` 状态和双人规则。V2.3 没有改变它的客户端掷骰与计分语义。

### 心跳与错误

```json
{"type":"ping","game":"gomoku","data":{}}
```

服务端返回：

```json
{"type":"pong","game":"gomoku","data":{}}
```

错误统一为：

```json
{"type":"error","game":"gomoku","message":"错误说明"}
```

## 五子棋结算与幂等

一局结束时，服务端从内存状态生成结算事件，再持久化到 `game_records`。`room_id + round_number` 唯一，重复结算不会生成第二条记录。积分以游戏记录 ID 作为 `related_id`，同一玩家、同一类型、同一局不会重复加分：

| 行为 | 分值 | 类型 |
| --- | ---: | --- |
| 完成一局（双方） | +1 | `GAME_PLAY` |
| 赢得一局（胜者） | +5 | `GAME_WIN` |
| 连续第三场获胜（胜者） | +10 | `SPECIAL_EVENT` |

若持久化暂时失败，服务端会重试一次，并把结算事件放回房间等待后续操作再次保存；客户端会收到“成长记录暂时保存失败”的错误提示。

## 向后兼容

旧的 `/api/games/dice/rooms` 和 `/ws/games/dice/{room_code}` 继续保留，并由同一个 `GameRoomManager` 处理。旧连接仍接收 `room_state` 格式；V2 统一连接接收 `state + game + data` 格式。五子棋只使用统一入口。

## 扩展新游戏的约束

后续游戏接入时必须：

1. 在 `games` 注册目录，并只在玩法、服务端校验和前端页面都完成后改成 `available`。
2. 在服务端实现权威的动作验证、状态序列化和胜负判定，客户端不拥有最终裁决权。
3. 复用 `/ws/game/{room_code}` 的消息信封，不为每个新游戏复制一套房间基础设施。
4. 使用 `game_players`、`game_records` 保存玩家和完成记录；V2.5 及之后的持久回合制游戏使用 `game_sessions` 和 `expected_version`。
5. 同步补充积分幂等、后端测试、微信真机双设备验收和本文档。
