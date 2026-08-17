# LoveOS V3 AI 重构报告

## 结果

六个游戏均可由 `AI_PROVIDERS` 解析，难度统一为 `random/rule/strategy`，游戏决策不调用 LLM 或外部网络。

## 本轮变更

- 新增服务端 `DiceAI`：二项分布估算、wild-one 规则、合法叫骰、对手历史 bluff rate；
- 五子棋：候选点排序、胜/挡优先、有界第二层对手威胁评估、256 局面 LRU；
- provider 实例按 `(game_type, level)` 复用，使缓存真实生效；
- `AIDecision` 增加 `budget_ms` 与 `within_budget`；
- 插件 AI level 与 provider level 由测试逐项对齐；
- 斗地主继续使用已有牌型枚举和保炸弹策略，没有复制规则。

## 性能与稳定性

五子棋 strategy AI 本地 100 次 P95 为 0.648 ms，低于 100 ms 平台预算。相同非随机局面返回相同动作；引擎仍会二次验证动作合法性。

## 兼容性

公开 AI action 仍使用已有 `action` envelope；API、游戏规则、胜负和 UI 未改变。小程序离线骰子 AI 保留，避免无网络场景退化。
