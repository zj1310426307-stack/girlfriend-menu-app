# V2.6 中国象棋、游戏数据中心与 AI 陪伴

## 当前能力

V2.6 在 V2.5 `GameEngine + GameSessionStore` 上增量接入中国象棋，不另建房间或积分链路。服务端持有完整棋局，客户端只提交来源坐标、目标坐标和 `expected_version`。

- 9×10 标准棋盘，红方先行。
- 支持车、马、相/象、仕/士、帅/将、炮、兵/卒。
- 校验马腿、象眼、不过河、九宫、炮架、过河兵、将帅照面、自陷将军。
- 无合法着法时判负；支持认输、将军提示和棋谱落库。
- 同一方连续第三次将军会被拒绝，作为首版长将保护；后续可在不改变接口的情况下升级为完整循环局面裁定。
- AI `random` 从合法着中随机选择；`rule` 优先吃子与将军。客户端不能提交 AI 点数、棋盘或指定 AI 落子。

## 状态与并发

象棋复用 `game_sessions`：

```text
client MOVE(from_pos, to_pos, expected_version)
  -> API 鉴权当前房间成员
  -> ChessGame 校验规则
  -> AI 在服务端自动应手（AI 模式）
  -> compare-and-swap 保存 version + 1
  -> 追加 chess_moves
  -> 完成时写 game_records、积分、成就、统计和记忆
```

同一版本被另一端抢先更新时返回 HTTP 409。前端刷新后重新选择棋子，不覆盖新棋局。

## 数据库

Alembic `20260809_07` 新增：

| 表 | 作用 |
| --- | --- |
| `chess_games` | 房间、红黑玩家、胜者、步数、时长 |
| `chess_moves` | 按步号保存棋子、起止坐标和可读棋谱 |
| `ai_players` | 各游戏 AI 角色、等级与透明配置 |
| `game_statistics` | 从完成记录重建的玩家/游戏类型统计 |
| `game_memories` | 只属于当前 `customer_id` 的游戏记忆 |

迁移同时把 `chinese_chess` 设为 `available`，增加“楚河初遇”“棋逢知己”和五子棋 20 胜成就。迁移不修改订单、评价或既有游戏数据，已验证全新升级、回退到 `20260809_06`、再升级。

## API

所有玩家私有接口都需要 `X-Customer-Id`。创建/加入仍需邀请码。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/games/chess/create` | 创建情侣房或 AI 训练局 |
| POST | `/api/games/chess/join` | 加入黑方席位 |
| POST | `/api/games/chess/move` | 落子、认输或聊天 |
| GET | `/api/games/chess/{room_code}/state` | 查询持久棋局 |
| GET | `/api/games/chess/{game_id}/history` | 原房间成员查看棋谱 |
| POST | `/api/games/{game_type}/ai/move` | 仅推进服务端当前 AI 回合；不接受客户端棋盘 |
| GET | `/api/games/ai/players` | AI 角色目录 |
| GET | `/api/games/ranking` | 我的战绩和共同房间月榜 |
| GET | `/api/games/memories/my` | 私人游戏记忆 |
| GET | `/api/games/ai/summary` | 可解释的今日陪伴小结 |

落子示例：

```json
{
  "room_code": "A88888",
  "action": "MOVE",
  "expected_version": 3,
  "from_pos": "a7",
  "to_pos": "a6"
}
```

排行榜只包含当前设备参与过的共同房间，其他玩家显示为脱敏“搭档·后四位”，不返回完整 `customer_id`。AI 日报是确定性规则摘要，只读取当前设备的用餐、完成游戏、积分和常点菜，不调用外部大模型，也不伪装成聊天结论。

## 小程序页面

- `pages/games/chess/index`：情侣/AI 大厅、棋盘、将军状态、棋谱、认输和同步。
- `pages/games/ranking/index`：个人战绩、共同房间月榜、热门游戏。
- `pages/games/ai/index`：今日数据摘要、AI 角色目录、私人游戏记忆。
- `ChessBoard`、`ChessPiece`、`MoveHistory`、`AIChat` 保持展示职责，规则与事实仍归服务端。

## 验证

```bat
cd /d D:\my-project\girlfriend-menu-app\backend
.venv\Scripts\python.exe -m pytest tests -q

cd /d D:\my-project\girlfriend-menu-app\miniprogram
npm run build:weapp
npm run test:v26
```

后端测试覆盖七类棋子、阻挡、过河/九宫、将帅照面、自陷将军、长将保护、AI 合法着、房间鉴权、乐观锁、棋谱、结算、积分、成就、统计、记忆和日报。
