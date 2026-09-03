# LoveOS V3 游戏中心现状审计

审计日期：2026-08-17

## 结论

仓库已经具备游戏平台骨架，不需要再新建一套并行 `game_engine`。本轮沿用以下唯一事实源：

- `backend/games/core`：纯规则引擎契约、房间/玩家/状态与结算基础；
- `backend/games/registry.py`：六个生产游戏及兼容别名；
- `backend/ai/registry.py`：本地、无网络的统一 AI provider；
- `backend/game_runtime`：骰子与五子棋实时房间、快照和恢复；
- `backend/services` + `backend/repositories`：事务、记录、回放、奖励与查询；
- `miniprogram/src/pages/games`：小程序分包游戏页面。

## 六个生产游戏

| 持久类型 | 兼容别名 | 权威状态源 | 传输 | AI |
| --- | --- | --- | --- | --- |
| `dice` | - | 实时房间 + `game_states` | HTTP + WebSocket | 概率/历史模型 |
| `gomoku` | - | 实时房间 + `game_states` | HTTP + WebSocket | 随机/规则/策略 |
| `aeroplane` | `flight` | 飞行棋版本化状态服务 | HTTP | 随机/规则/策略 |
| `landlord` | - | `game_sessions` | HTTP | 随机/规则/策略 |
| `jungle` | `animal` | `game_sessions` | HTTP | 随机/规则/策略 |
| `chinese_chess` | `chess` | `game_sessions` | HTTP | 随机/规则/策略 |

## 主链路

1. API 只处理认证、输入和响应模型。
2. Service 选择游戏插件并编排事务。
3. 规则引擎验证并生成 JSON-safe 状态。
4. Repository 写入统一房间、会话、动作、记录和回放表。
5. WebSocket 管理器只持有进程内 socket 与 leased room，快照落到可恢复状态存储。
6. 小程序继续调用原 API/WS 路径，不感知内部插件迁移。

## 本轮发现并修复的架构缺口

- 插件原先没有显式声明生命周期、状态适配器和传输能力；
- 通用重连按游戏名写分支，扩展一个游戏要修改兼容服务；
- 实时管理器直接负责五子棋引擎的构造与 JSON 恢复；
- 骰子概率 AI 只存在于小程序，未进入统一服务端 AI 能力表；
- AI 决策只有耗时，没有可检查的预算结果；
- 五子棋策略相同局面存在随机平局选择，没有可复用的局面缓存。

## 保留项

游戏入口、历史记录、成就、默契积分、排名、房间恢复、回放、公开 API、WebSocket 消息、数据库表和迁移全部保留。
