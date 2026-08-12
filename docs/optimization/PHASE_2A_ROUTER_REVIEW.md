# Phase 2A FastAPI Router 模块化审查

> 完成日期：2026-08-12（Asia/Shanghai）
>
> 变更性质：纯后端路由组织重构；不改变业务逻辑、API 契约、数据库模型、Alembic、小程序或游戏规则。

## 1. 改造前 main.py 职责

改造前 `backend/main.py` 共 1,725 行、62,111 bytes，同时承担：

- FastAPI 初始化、CORS、静态目录和请求日志中间件；
- lifespan、种子数据和三个后台维护循环；
- 普通端/管理端认证依赖；
- 用户、通知、菜品、收藏、订单、评价、情侣中心和管理统计 HTTP 路由；
- 六类游戏的 HTTP 路由；
- 管理订单、大话骰和统一游戏 WebSocket 协议；
- 图片上传验证。

这种结构没有直接改变运行能力，但使权限依赖、WebSocket 生命周期和业务路由容易在同一文件中发生非预期耦合。

## 2. 改造后目录

```text
backend/
├── main.py
└── api/
    ├── __init__.py
    ├── dependencies.py
    ├── router.py
    └── routes/
        ├── system.py
        ├── auth.py
        ├── users.py
        ├── dishes.py
        ├── orders.py
        ├── couple.py
        ├── notifications.py
        ├── admin.py
        ├── games.py
        ├── uploads.py
        └── websocket.py
```

`main.py` 现在只保留应用创建、生命周期任务、中间件、静态目录和总 Router 注册。

## 3. main.py 大小变化

| 指标 | Before | After | 变化 |
| --- | ---: | ---: | ---: |
| 行数 | 1,725 | 186 | -89.2% |
| Bytes | 62,111 | 6,732 | -89.2% |

本阶段没有为了缩短文件而移动业务规则；规则和状态转换仍由既有 service、crud、realtime 和游戏引擎负责。

## 4. Router 职责

| 模块 | 职责 |
| --- | --- |
| `system.py` | 根路径、liveness、readiness |
| `auth.py` | customer session、claim、recover、refresh、revoke、admin login |
| `users.py` | 当前用户资料和 presence |
| `dishes.py` | 菜品、收藏、个人喜欢排行和管理菜品 |
| `orders.py` | 下单、历史、详情、评价、管理订单、状态更新和订单广播 |
| `couple.py` | 共同记忆、纪念日、资料、统计、积分和每日任务 |
| `notifications.py` | 通知列表、未读数和已读状态 |
| `admin.py` | 管理驾驶舱、订单统计和游戏统计 |
| `games.py` | 游戏目录、房间、恢复、回放、AI 和所有 HTTP 动作入口 |
| `uploads.py` | 管理图片上传与原有 5MB/格式验证 |
| `websocket.py` | 管理订单、统一游戏和旧大话骰 WebSocket 协议 |
| `dependencies.py` | 管理鉴权、客户身份、legacy bridge、Bearer 解析和限流 |

## 5. API Compatibility

- HTTP 操作：87，迁移前后保持一致。
- WebSocket 路径：3，迁移前后保持一致。
- URL、HTTP Method、request schema、response model、status code 和 deprecated 标记按原装饰器搬迁。
- 管理鉴权、客户身份和 legacy header 使用同一 `api.dependencies` 实现。
- 订单创建/状态/评价仍调用原通知与 `order_event_hub.broadcast`。
- 游戏恢复、房间租约、结算重试、回放、奖励和私有骰子过滤逻辑未修改。
- 新增 `tests/test_router_contract.py`，硬编码并校验全部 HTTP method/path 和三条 WebSocket 路径，同时拒绝重复注册。

项目没有 OpenAPI 生成客户端命令；本阶段没有 API 变化，因此无需生成前端接口文件。现有小程序 API 调用文件未修改。

## 6. 测试结果

- 后端全量：`81 passed`，原 79 项无减少，新增 2 项 Router 契约测试。
- Python import/compile：通过。
- `npm run test:games`：通过。
- `npm run test:landlord`：通过。
- `npm run build:weapp`：通过，Taro 4.2.0，13.03 秒。
- 当前路由统计：87 个 `/api` HTTP 操作、3 个 `/ws` WebSocket 路径。
- `git diff --check`：完成收口时再次验证。

## 7. Database Change

数据库模型变化：0。

Phase 2A 没有修改 `models.py`、SQLAlchemy 表、字段、约束或数据。工作区中现存的 `customer_sessions` 相关修改属于已经完成的 Phase 1，不属于本阶段。

## 8. Migration

Migration 变化：0。

当前 Alembic head 仍为 Phase 1 的 `20260811_11`。Phase 2A 没有新增、修改或删除任何迁移文件。

## 9. 风险与回滚

- `games.py` 和 `websocket.py` 仍较大，但它们已经与应用装配隔离；继续拆分必须以独立 Phase 进行，不能在本阶段修改游戏状态或协议。
- Python 依赖仍使用项目当前的顶层模块导入方式；如果未来把后端安装为正式 package，需要单独设计绝对包路径，不能与本次行为保持型重构混做。
- 自动化覆盖了协议、恢复、权限和主要业务，但 Render 冷启动、Neon 生产连接以及微信双真机仍需要部署后冒烟。

回滚只需要恢复旧 `main.py` 并删除 `api/` 路由注册改动；不需要数据库降级，不影响生产数据。由于本阶段没有 API 和小程序变化，后端可独立回滚。

## 10. 是否进入 Phase 2B

**建议在受控环境完成一次后端部署冒烟后进入 Phase 2B。**

进入前至少确认：`/api/health`、`/api/ready`、设备恢复、提交订单、管理改状态、一条游戏 HTTP 动作和一条 WebSocket 重连均正常。不要把 Phase 2A 路由搬迁与 Phase 2B 的 service 拆分放在同一次生产发布中。
