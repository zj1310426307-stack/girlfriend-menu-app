# V2.1 游戏中心通信协议

## 目标与边界

V2.1 只建立统一大厅、房间元数据和通信协议。大话骰是第一个迁入的玩法；五子棋等游戏只登记目录，不在本版本伪造玩法。游戏系统不读取或修改点菜、订单与评价业务。

持久化边界：

- `games` 保存游戏目录和开放状态。
- `game_rooms` 保存房间码、类型、创建者、人数和生命周期状态。
- 棋盘、骰子、轮次、连接和计分仍是实时内存状态；服务重启后不会恢复进行中的一局。

## HTTP API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/games` | 返回全部游戏及 `available/coming_soon/maintenance` 状态 |
| POST | `/api/games/rooms` | 为已开放游戏创建房间 |
| GET | `/api/games/rooms/{room_code}` | 查询房间类型、人数和状态 |

创建房间示例：

```json
{
  "game_type": "dice",
  "creator": "gf_设备标识",
  "invite_code": "邀请码"
}
```

房间状态只使用：`waiting`、`playing`、`finished`。

## WebSocket

统一入口：

```text
/ws/game/{room_code}
```

所有客户端消息使用同一信封：

```json
{
  "type": "move_or_action",
  "game": "game_type",
  "data": {}
}
```

加入大话骰房间：

```json
{
  "type": "join",
  "game": "dice",
  "data": {
    "player_id": "gf_xxx",
    "name": "我",
    "invite_code": "邀请码"
  }
}
```

大话骰操作：

```json
{"type":"roll","game":"dice","data":{"values":[1,2,3,4,5]}}
{"type":"bid","game":"dice","data":{"quantity":3,"face":5}}
{"type":"challenge","game":"dice","data":{}}
{"type":"rematch","game":"dice","data":{}}
```

服务端状态：

```json
{
  "type": "state",
  "game": "dice",
  "room_code": "ABC234",
  "data": {
    "phase": "bidding",
    "players": [],
    "turn_id": "gf_xxx",
    "current_bid": null
  }
}
```

错误统一为：

```json
{"type":"error","game":"dice","message":"错误说明"}
```

## 向后兼容

旧的 `/api/games/dice/rooms` 和 `/ws/games/dice/{room_code}` 暂时保留，并由同一个 `GameRoomManager` 处理。旧连接收到原 `room_state` 格式，新连接收到统一 `state + game + data` 格式。

## 新游戏接入约束

后续五子棋接入时需要：

1. 在 `games` 中把 `gomoku` 改为 `available`。
2. 为 `GameRoomManager` 注册五子棋的初始化、操作验证、状态序列化和胜负判断处理器。
3. 客户端复用 `gameSocket.js`，只实现棋盘 UI 与 `move` 数据。
4. 服务端负责轮次、落点合法性和胜负判断，客户端不拥有最终裁决权。
