# V2.3 游戏中心通信协议

## 目标与边界

游戏大厅、房间元数据、大话骰和双人五子棋共用一套实时通信入口。V2.3 新增服务端权威的 15×15 五子棋与持久游戏记录，不读取或修改点菜、订单和评价主流程。

持久化边界：

- `games` 保存游戏目录和开放状态；当前 `dice`、`gomoku` 为 `available`。
- `game_rooms` 保存房间码、类型、创建者、人数、生命周期状态和完成时间。
- `game_players` 保存玩家设备标识、席位、房间局分和加入时间。
- `game_records` 保存每个房间每一局的胜者、时长和服务端结果快照。
- `love_scores` 保存五子棋参与、获胜和三连胜积分。
- WebSocket、正在进行的棋盘、骰子、轮次和连接对象仍是单进程内存状态；服务重启后不会恢复未完成的一局。

## HTTP API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/games` | 返回全部游戏及 `available/coming_soon/maintenance` 状态 |
| POST | `/api/games/rooms` | 为已开放游戏创建房间 |
| GET | `/api/games/rooms/{room_code}` | 查询房间元数据、玩家席位和状态 |
| GET | `/api/games/records/my` | 查询当前设备最近游戏记录，需 `X-Customer-Id` |
| GET | `/api/admin/games/stats` | 管理端游戏统计，需 Bearer token |

创建五子棋房间示例：

```json
{
  "game_type": "gomoku",
  "creator": "gf_device_id",
  "invite_code": "邀请口令"
}
```

房间状态只使用 `waiting`、`playing`、`finished`。房间码由后端生成，为去掉易混字符的 6 位大写字母或数字。

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
4. 使用 `game_players`、`game_records` 保存玩家和完成记录；快变的对局状态只有在引入专门状态存储后才能跨进程恢复。
5. 同步补充积分幂等、后端测试、微信真机双设备验收和本文档。
