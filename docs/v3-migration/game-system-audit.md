# LoveOS V3 游戏系统审计

审计日期：2026-08-17

## 现状结论

游戏中心已经包含统一房间、状态、回放、结算、重连和纯规则引擎，V3 的正确方向是把这些能力提升为“可注册插件平台”，不是另建 `game_engine` 并复制代码。

## 游戏能力清单

| 游戏 | 服务端规则/引擎 | AI | 在线房间 | 回放/记录 | 前端渲染 |
| --- | --- | --- | --- | --- | --- |
| 飞行棋 | `flight_service.py`、`flight.py` | `ai/flight_ai.py` | 是 | 是 | Taro 组件棋盘 |
| 五子棋 | `gomoku.py` | `ai/gomoku_ai.py` | 是 | 是 | Taro 棋盘 |
| 斗地主 | `games/landlord/*` | 规则 AI | 是 | 是 | Taro 手牌/牌桌 |
| 斗兽棋 | `games/animal/*` | 规则 AI | 是 | 是 | Taro 棋盘 |
| 中国象棋 | `games/chess/*` | 规则/搜索 AI | 是 | 是 | Taro 棋盘 |
| 骰子 | `dice_rules.py` | 页面轻量 AI | 是，独立 WS | 房间状态 | 原生 Canvas 场景 |
| 转盘 | 前端随机交互 | 无 | 否 | 否 | Taro 页面 |

## 已共享能力

- `games/core/GameEngine`：动作、序列化和视角过滤契约。
- `games/core/room.py`、`state.py`、`player.py`：共享领域对象。
- `game_runtime/manager.py`：在线房间实例与连接管理。
- `services/game_persistence_service.py`：版本化状态和幂等动作。
- `services/game_settlement_service.py`：幂等奖励、记忆、任务、通知和回放。
- `game_recovery_service.py`：持久化回放和恢复。
- `core/game_room_lease.py`：多实例房间所有权租约。
- `GameAction.client_action_id` + 版本字段：动作幂等和并发保护。

## 缺口

1. 没有集中式 `GamePlugin` 描述；游戏列表、房间动作和 AI 能力仍通过条件分支发现。
2. 统一 `GameEngine` 目前只被部分回合制游戏完整实现，飞行棋/五子棋仍有旧服务边界。
3. `game_runtime/manager.py` 同时承担注册、连接、广播和游戏分发，扩展成本高。
4. AI 难度字符串有共同约定，但缺少能力发现、统一超时和耗时观测。
5. 骰子使用独立 WebSocket；需要保留协议，同时通过 adapter 接入统一诊断。

## V3 插件契约目标

每个插件声明：

- 稳定 `game_type`；
- 支持的模式、人数和 AI 难度；
- 创建引擎/恢复状态的方法；
- 允许动作的服务入口；
- 是否支持隐藏信息、回放、在线房间；
- 旧 API adapter 列表。

注册表只负责发现和分发，不包含具体规则。具体引擎必须继续保持纯 Python，不依赖 FastAPI、SQLAlchemy、数据库或网络。

## AI 审计

### 当前结构

`ai/base.py` 已定义 `AIPlayer.choose_action(state, player_id)`，难度为 `random`、`rule`、`strategy`。斗地主、斗兽棋和象棋的顶层 AI 文件主要是兼容导入；飞行棋和五子棋保留独立实现。

### V3 目标

- `strategy`：统一策略协议和结果元数据。
- `rule_ai`：确定性规则或启发式决策。
- `search_ai`：有明确节点/时间预算的轻量搜索。
- `personality`：只改变文案/风格，不改变合法动作约束。
- 游戏决策不调用远程大模型；聊天、剧情、互动文案与游戏动作分离。

旧 `ai/*.py` 和 `games/*/ai.py` 保留为兼容入口，直到所有调用方和回归测试迁移完成。

## 飞行棋决策

“停止维护并立即替换 Phaser”在当前证据下不可执行：Phaser 是渲染/游戏框架，不是可直接替代现有服务端规则、房间、积分和 LoveOS 事件的 Ludo 规则实现。

V3 采取以下路径：

1. 冻结旧公开规则和 API 行为。
2. 将规则、应用服务和渲染器边界写成契约。
3. 保留现有 Taro 渲染器作为生产实现。
4. 在独立实验分包做 Phaser Canvas PoC，验证真机、包体、触控、后台恢复和许可证。
5. 只有 PoC 全部达标，才把新渲染器挂到同一插件；服务端状态和旧 API 不变。

## 验收护栏

- 所有现有游戏测试继续通过。
- 旧 HTTP/WS 路径完整保留。
- 同一动作在旧入口和插件入口得到等价状态。
- AI 动作始终合法，规则/策略模式本地完成。
- 游戏规则模块继续通过 import-linter 纯度契约。
- 不在未验证的框架迁移中删除原渲染器。
