# V2.2 情侣积分系统

## 目标与边界

情侣积分把点餐、制作、评价和未来游戏事件记录到同一条成长流水。它不改变订单、评价或游戏的原有业务状态，也不允许普通客户端直接修改积分。

当前仍使用微信本地保存的 `gf_customer_id` 识别一对情侣的设备数据。清除小程序缓存后会生成新的标识，旧积分不会自动关联到新设备；管理端和数据库中的旧记录不会丢失。

## 数据表

`love_scores` 是只追加的积分流水：

| 字段 | 说明 |
| --- | --- |
| `id` | 流水编号 |
| `customer_id` | 当前设备匿名标识 |
| `score` | 本次增加的积分 |
| `type` | 固定行为类型 |
| `description` | 用户可读的来源说明 |
| `related_id` | 关联订单或未来游戏记录编号，可空 |
| `created_at` | 发生时间 |

`customer_id + type + related_id` 唯一。自动计分都有业务关联编号，因此相同业务事件重试不会重复记账；无关联编号的管理补录允许多次发生。

支持的类型：

- `ORDER_COMPLETE`
- `ORDER_REVIEW`
- `GAME_WIN`
- `GAME_PLAY`
- `COOK_COMPLETE`
- `SPECIAL_EVENT`

本版本未开发新游戏。`GAME_WIN` 与 `GAME_PLAY` 只为后续统一游戏记录预留，不从当前内存骰子房间自动计分。

## 自动计分规则

| 事件 | 分值 | 类型 |
| --- | ---: | --- |
| 订单首次变为“已完成” | +10 | `ORDER_COMPLETE` |
| 提交五星评价 | +5 | `ORDER_REVIEW` |
| 从历史订单“再做一次”并提交新订单 | +2 | `SPECIAL_EVENT` |

四星及以下评价仍正常保存，但不加五星奖励。重复提交评价由原有订单唯一评价规则阻止；重复把同一个订单改为“已完成”也不会重复加分。

## 默契值模型

默契值不是积分余额，而是三项信号的加权结果：

```text
默契值 = 近期互动 × 40% + 共同经历 × 30% + 满意反馈 × 30%
```

- 近期互动：近 30 天积分事件数量，设置上限，避免刷单无限放大。
- 共同经历：有唯一业务来源的事件数量，包括订单完成、五星评价和再次点单。
- 满意反馈：当前设备历史评价的平均分，并按评价数量增加可信度。

等级：

| 默契值 | 等级 |
| ---: | --- |
| 0～49 | 初识 |
| 50～99 | 熟悉 |
| 100～199 | 默契搭档 |
| 200 及以上 | 灵魂搭档 |

接口同时返回 `points_total` 和 `month_score`，分别表示累计积分与本月积分，避免把积分流水与默契值混为一谈。

## API 与权限

### 查询默契值

```http
GET /api/couple/score
X-Customer-Id: gf_xxx
```

### 查询积分流水

```http
GET /api/couple/score/history
X-Customer-Id: gf_xxx
```

### 管理补录

```http
POST /api/couple/score/add
Authorization: Bearer <admin_token>
X-Customer-Id: gf_xxx
Content-Type: application/json

{
  "type": "SPECIAL_EVENT",
  "score": 20,
  "description": "周年纪念日"
}
```

补录接口必须同时提供管理令牌和客户标识。普通情侣页面只调用两个查询接口；订单与评价奖励由后端自动触发，防止修改客户端伪造积分。

## 页面

- `pages/couple/index`：默契值、本月互动、最新积分和管理入口。
- `pages/couple/score`：按日期分组的积分流水。
- `pages/couple/records`：第一次点餐、完成次数、游戏次数和最爱菜品。
- `pages/couple/achievements`：根据已有数据即时计算的成就展示。

成就目前不单独建表，全部由积分、订单和评价数据派生，因此不会出现成就与业务数据不一致的问题。

## 迁移与验证

迁移版本为 `20260809_03`，只新增 `love_scores` 表和索引。Render 启动命令中的 `alembic upgrade head` 会自动升级 Neon PostgreSQL；旧数据不删除、不重建。

本地验证：

```bat
cd /d D:\my-project\girlfriend-menu-app\backend
.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.venv\Scripts\python.exe -m pytest -q

cd /d D:\my-project\girlfriend-menu-app\miniprogram
npm run build:weapp
```
