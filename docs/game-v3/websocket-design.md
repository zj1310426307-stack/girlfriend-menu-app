# LoveOS V3 WebSocket 设计

## 公共协议

生产路径保持：

- `/ws/game/{room_code}`：统一 V2 envelope；
- `/ws/games/dice/{room_code}`：legacy 骰子路径；
- `/ws/admin/orders`：管理通知。

客户端动作继续是 `{type, game, data}`，服务器状态继续是 `{type: "state", game, room_code, data}`。未新增必填字段。

## 服务端职责

1. PostgreSQL 保存房间、座位、租约、动作和结算；
2. `GameRoomManager` 保存本进程 socket、锁与 write-behind 队列；
3. `engine_codec` 保存游戏引擎构造/序列化/恢复差异；
4. `game_state_store` 保存可恢复快照；
5. viewer-filtered state 阻止骰子私有信息泄露；
6. 结算先持久化 pending record，再执行奖励、回放、通知并 finalize。

## 重连

重连凭证仅保存 SHA-256 hash。进程内房间消失后，API 从持久化房间和快照恢复，重新装载座位，再按 viewer 返回状态。五子棋 engine codec 会恢复棋盘、玩家、回合、胜者、历史和局数。

## 为什么不引入 Colyseus

Colyseus 会增加 Node/TypeScript 房间服务、部署单元和跨服务一致性协议，而当前系统已具备 WS、lease、Redis 可选层、幂等、重连和回放。没有可量化收益时不制造双写和双 owner。
