# LoveOS V3 Game Platform 设计

## 设计目标

以现有 `games/core` 为唯一规则核心，把“新增游戏需要修改哪些分支”收敛到插件能力表，同时保留全部生产 API、状态表和页面。

## 核心组件

| 组件 | 文件 | 单一职责 |
| --- | --- | --- |
| 生命周期枚举 | `backend/games/core/lifecycle.py` | create/join/start/action/validate/finish/recover/replay |
| 游戏插件 | `backend/games/core/plugin.py` | 类型、别名、人数、模式、AI、传输、状态 adapter |
| 游戏注册表 | `backend/games/registry.py` | 六个生产游戏唯一目录 |
| 纯引擎接口 | `backend/games/core/engine.py` | apply/serialize/public_state |
| 恢复 adapter | `backend/services/game_compatibility_service.py` | 按状态所有权分派旧服务 |
| 实时 engine codec | `backend/game_runtime/engine_codec.py` | 引擎构造、快照、恢复 |
| 实时 transport | `backend/game_runtime/manager.py` | socket、锁、广播、write-behind |
| AI 注册表 | `backend/ai/registry.py` | 本地 provider 与难度 |

## 生命周期

所有插件必须显式支持：

`create -> join -> start -> action -> validate -> finish -> recover -> replay`

注册阶段会拒绝缺少基础操作、replay/realtime 标志与能力不一致、重复 alias/transport 的插件，问题在应用启动时暴露，而不是运行中静默降级。

## 状态所有权

- `REALTIME_ROOM`：dice、gomoku；
- `FLIGHT_STATE`：aeroplane；
- `VERSIONED_SESSION`：landlord、jungle、chinese_chess。

兼容恢复服务只查看 `plugin.state_adapter`，不再按游戏名判断。状态仍由原服务写入，避免迁移中双写。

## 扩展一个新游戏

1. 实现纯规则引擎或明确 legacy adapter；
2. 在唯一 `GAME_PLUGINS` 注册能力；
3. 若需要 AI，在 `AI_PROVIDERS` 注册本地 strategy；
4. 若走实时房间，实现一个 engine codec；
5. 增加规则、非法动作、边界、恢复和 replay 测试；
6. API 只增加兼容入口，不在路由中写规则。

## 不采用第二套目录的原因

另建 `backend/game_engine` 会复制 `games/core`、`game_runtime`、Service 和 Repository 的职责，产生两个 registry 和两套状态语义。本轮使用能力对象补齐现有架构缺口，避免形式重构。
