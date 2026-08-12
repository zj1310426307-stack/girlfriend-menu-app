# 2.10.0 游戏长期稳定化

## 目标

本版本不新增游戏，集中修复“能打开但不能长期玩”的问题：入口堆叠、继续游戏失效、网络断开无反馈、重复点击、未确认棋面、实时状态只在进程内存以及大话骰重连隐私。

## 前端变化

- 游戏大厅改为数据驱动的六款固定游戏卡片；建房、加入、模式和难度回到各游戏自己的大厅。
- “继续上次”带房间码进入后，原房间成员自动使用重连凭证或成员鉴权状态接口恢复；邀请链接的新玩家仍停留在加入页。
- 飞行棋、斗地主、斗兽棋和中国象棋共用 `GameSyncBar`，持续显示 `syncing / online / offline`，离线时保留明确重试入口。
- 串行轮询失败后指数退避，最大 12 秒；恢复成功立即清除离线错误。
- 动作使用同步锁阻止同一渲染帧内的重复提交。
- 斗兽棋和中国象棋取消直接改本地棋盘的乐观落子；服务器确认后才展示结果。认输增加二次确认。
- 大话骰和五子棋共享 Socket 增加指数退避、随机抖动、有界 20 条离线队列和手动退出清理。

## 后端变化

- 大话骰和五子棋内部快照写入现有 PostgreSQL `game_states`；内存与 Redis 只作为缓存层。
- 快照包含棋盘/骰子、轮次、耗时、动作记录和待结算事件，新的服务进程可以恢复。
- `/api/games/reconnect` 对实时游戏先恢复权威快照，再按当前成员生成查看者视图。
- 大话骰未开盅时只返回 `my_dice`，`all_dice` 固定为 `null`；内部完整骰点不进入公开响应。
- 完成事件在结算成功后才确认清除，降低进程在积分/回放写入期间退出造成丢记录的风险。

## 设计参考

只借鉴架构与交互原则，没有复制第三方美术、商标或音效：

- [boardgame.io](https://github.com/boardgameio/boardgame.io)（MIT）：纯状态转移、回合与操作日志。
- [RLCard](https://github.com/datamllab/rlcard)（MIT）：斗地主合法动作和私有信息边界。
- [ludo-js](https://github.com/RoJac88/ludo-js)（MIT）：飞行棋显式回合状态机和可移动提示。
- [Jungle Chess](https://github.com/barbanevosa/jungle-chess)（MIT）与 [Xiangqi React](https://github.com/ryoi/xiangqi)（MIT）：棋类规则、历史和结果层。
- [Dice Box](https://github.com/3d-dice/dice-box)（MIT）与 [Spin Wheel](https://github.com/CrazyTim/spin-wheel)（MIT）：状态与表现分离、响应式触控和停止回调。

## 自动验证

```text
backend/.venv/Scripts/python.exe -m pytest -q
cd miniprogram
npm run test:games
npm run test:landlord
npm run build:weapp
```

重点回归：PostgreSQL 重启恢复、骰子重连隐私、Socket 重连/队列、游戏大厅恢复链接、四个轮询页面连接状态、象棋/斗兽棋无幽灵落子。

## 仍需继续的长期工作

- 多实例 WebSocket 房间所有权和分布式锁。
- REST 游戏 finished 状态的后台幂等 reconciler。
- 房间 TTL、放弃状态和定时清理。
- HTTP 动作 `client_action_id` 幂等。
- 象棋/斗兽棋回合超时、最大回合和重复局面和棋。
- 两台真实手机完成弱网、切后台、断线恢复和再来一局验收。
