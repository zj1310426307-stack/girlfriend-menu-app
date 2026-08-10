# 2.9.1 游戏顺滑与全模式人机

## 能力范围

| 游戏 | 情侣模式 | 人机模式 | AI 与随机来源 |
| --- | --- | --- | --- |
| 大话骰 | WebSocket 双人房间 | 单机 3D 多 AI | 单机规则 AI；在线骰子由服务端生成 |
| 五子棋 | WebSocket 双人房间 | 一人对五子棋 AI | 服务端胜负校验与 AI 落子 |
| 飞行棋 | HTTP 持久房间 | 一人对飞行棋 AI | 服务端骰子、移动与胜负 |
| 斗地主 | 两位真人 + 一位 AI | 一位真人 + 两位 AI | 服务端洗牌、牌型、回合与 AI |
| 斗兽棋 | HTTP 版本房间 | 一人对森林 AI | 服务端规则与 AI 移动 |
| 中国象棋 | HTTP 版本房间 | 一人对象棋 AI | 服务端规则、AI 移动与棋谱 |

转盘是本地决策工具，不存在对手，因此不设置人机模式。

## 创建参数

以下创建请求新增或统一使用字段：

```json
{
  "mode": "couple",
  "difficulty": "rule"
}
```

- `mode`：`couple` 或 `ai`。
- `difficulty`：`random`、`rule`；五子棋额外开放 `strategy`。
- 老客户端不传字段时默认 `couple + rule`，原情侣房间保持兼容。

对应入口：

- `POST /api/games/rooms`：五子棋人机房间。
- `POST /api/games/flight/create`：飞行棋情侣/人机。
- `POST /api/games/landlord/create`：斗地主情侣/人机。
- 斗兽棋和中国象棋继续使用原有创建接口及相同字段。

## 公平与数据边界

- 五子棋 AI 只读取服务端棋盘，依次处理立即获胜、立即防守和局部棋形评分。
- 飞行棋客户端不能指定骰子；AI 也使用服务端 `secrets` 骰子。
- 斗地主客户端看不到 AI 或搭档的手牌，AI 只能读取它所属的服务端状态。
- AI 身份统一以 `ai_` 开头，不获得 Love Score、每日任务或月榜名次。
- 完成记录允许 AI 成为胜者，以保持战绩真实；只有人类玩家获得参与和获胜奖励。

## 顺滑性处理

- HTTP 情侣房间使用串行 `setTimeout` 轮询，避免固定 `setInterval` 造成并发请求。
- 页面隐藏时停止发请求；重新显示后继续。
- 等待加入约 2.4 秒同步，进行中约 1.2 秒同步；人机模式直接使用动作响应，不额外轮询。
- `game_sessions.version` 或飞行棋 `updated_at` 未变化时，不覆盖 React 状态，避免选择中的棋子被轮询清空。
- 五子棋 WebSocket 落子先显示安全的视觉预落子，服务端快照随后校正；AI 回合保留约 280ms 思考过渡。
- 动画只使用 `transform/opacity`，减少手机端布局抖动。

## 自动验证

- `backend/tests/test_game_ai_modes.py` 覆盖五子棋 AI 取胜、WebSocket AI 回合、飞行棋 AI 与斗地主双 AI 开局。
- 后端全量 `pytest` 和 `npm run build:weapp` 必须在交付前通过。
- 两台真机联机仍是体验版外部验收项，自动测试不能替代微信弱网、切后台和断线恢复验证。
