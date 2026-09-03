# LoveOS V3 游戏 AI 清单

审计日期：2026-08-17

## 原则

游戏胜负决策全部在本地规则/搜索/概率模型中完成，不调用 LLM、不访问网络。LLM 能力只允许服务于聊天、情侣故事或内容生成，不进入规则判定。

## Provider 清单

| 游戏 | 实现 | random | rule | strategy | 预算 |
| --- | --- | --- | --- | --- | --- |
| 大话骰 | `backend/ai/dice_ai.py` | 随机合法叫骰 | 概率阈值 | 概率 + 对手历史 | 100 ms |
| 五子棋 | `backend/ai/gomoku_ai.py` | 随机邻近点 | 胜/挡/线型 | 有界两层搜索 + 局面缓存 | 100 ms |
| 飞行棋 | `backend/ai/flight_ai.py` | 随机可走棋子 | 完成/起飞/吃子 | 风险与终点策略 | 100 ms |
| 斗地主 | `backend/games/landlord/ai.py` | 随机合法牌型 | 保炸弹的最小合法牌 | 主动消牌组合 | 100 ms |
| 斗兽棋 | `backend/games/animal/ai.py` | 随机合法步 | 规则估值 | 策略估值 | 100 ms |
| 中国象棋 | `backend/games/chess/ai.py` | 随机合法步 | 吃子/将军估值 | 有界两层搜索 | 100 ms |

## 统一入口

`AI_PROVIDERS.choose_action(game_type, state, player_id, level)` 负责：

1. 规范化 `flight/animal/chess` 别名；
2. 验证难度；
3. 复用 provider 实例，使有界缓存生效；
4. 验证动作 envelope；
5. 返回 `duration_ms`、`budget_ms` 和 `within_budget`。

## 重复实现判断

`backend/ai/chess_ai.py`、`animal_ai.py`、`landlord_ai.py` 是稳定导入 shim，不是第二套算法；删除会破坏旧 import。小程序离线骰子 AI 与服务端骰子 provider 分属离线 UI 和平台能力，当前不能删除任一方；两者使用相同 wild-one 概率语义。
