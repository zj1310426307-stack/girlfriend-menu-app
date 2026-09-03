# LoveOS V3 Continuous Optimization 01 兼容与迁移说明

- 日期：2026-08-24
- 适用分支：`feature/continuous-optimization-01`
- 适用范围：认证 activity 节流、小程序私有状态隔离、免费生产发布门

## 1. 兼容性总表

| 项目 | 结论 | 说明 |
| --- | --- | --- |
| 原 HTTP API | 完全兼容 | 路由、method、请求/响应字段、状态码和 bearer 格式均未调整 |
| 原 WebSocket 协议 | 兼容 | `session` 消息仍转发给页面；仅停止把未使用的 `room_session_token` 长期写入本机 storage |
| OpenAPI | 无合同变化 | 本轮不应生成新的 OpenAPI diff；以 `export_openapi.py --check` 为准 |
| 原数据库 | 完全兼容 | 无表、列、索引、约束或数据类型变化，不新增 Alembic revision |
| 服务端用户数据 | 完全兼容 | 客户、订单、游戏房间、积分、通知等数据不迁移、不删除 |
| 小程序本地临时数据 | 有意收紧 | 同一客户 token 刷新保留草稿；退出、过期或 owner 切换时删除客户私有临时数据 |
| 前端页面路由 | 完全兼容 | 页面路径、分包和跳转关系不变 |
| 核心业务规则 | 完全兼容 | 登录、授权、撤销、过期、下单和游戏规则不变 |
| 原环境变量名 | 兼容 | 未重命名或删除变量；示例中的秘密值改为空白，真实部署必须显式配置 |
| 原生产触发方式 | 运维行为调整 | 运行规格仍为免费；`autoDeploy` 从 true 改为 false，发布改为人工确认 |
| 原启动命令 | 可回退 | `alembic upgrade head && uvicorn ...` 仍可人工执行；仓库标准入口改为 `python serve.py` |
| 逻辑备份命令 | 参数收紧 | `PRODUCTION_API_ORIGIN`、`ADMIN_PASSWORD`、`ADMIN_INVITE_CODE` 现在都必须显式提供 |

## 2. 认证 activity 兼容说明

### 调整原因

旧实现每个已登录请求都会更新 `customer_sessions.last_seen_at`、`customers.last_seen_at` 并提交事务。该字段只用于活跃度观测，不应把所有读取请求变成远程数据库写入。

### 新语义

- 撤销、过期和客户停用仍在每个请求中查询数据库并立即判定。
- `last_seen_at` 最多延迟 5 分钟更新；超过窗口的第一个请求取得数据库条件更新 ownership。
- 同一窗口内的其他请求保持只读，不修改 ORM，也不 commit。
- `update_last_seen=False` 继续完全跳过 activity touch。
- token 生命周期、权限和业务动作时间不受影响。

### 数据迁移

无。现有时间戳保持原值，第一次超过窗口的认证会自然刷新。

### 回滚

回退 `customer_service` 的 activity helper 和 `authenticate()` 调用，即可恢复逐请求更新。无需执行 Alembic downgrade，也无需恢复数据。

## 3. 小程序本地存储迁移

### 3.1 键变化

| 数据 | 旧键 | 新行为 |
| --- | --- | --- |
| 购物车 | `gf_menu_cart` | 键名保留；退出、过期或 owner 变化时删除 |
| 复购草稿 | `gf_repeat_order_draft` | 键名保留；退出、过期或 owner 变化时删除 |
| 游戏重连 | `gf_game_reconnect_{ROOM}` | 不再读取；删除后由合法当前客户重新签发 |
| 游戏重连（新） | 无 | `gf_game_reconnect_v31_{encodedCustomerId}:{encodedRoom}`，读取必须同时提供 owner 和 room |
| room session secret | `gf_room_session_{ROOM}` | 停止写入；在会话边界清除 |
| legacy 设备 ID | `gf_customer_id` | 保留，继续支持身份恢复兼容 |
| 公共菜品缓存 | `gf_dishes_cache_v28` | 保留，不属于客户私有状态 |

### 3.2 为什么不自动迁移旧 reconnect token

旧键没有 customer owner，无法证明它属于当前登录客户。把它复制到新 owner 会重建原有越界风险，因此采用 fail-closed：只删除、不读取。合法客户仍可通过 bearer 保护的房间状态接口恢复自己的房间，随后重新签发 scoped reconnect token。

### 3.3 用户影响

- 正常 token 刷新且 customer ID 不变：购物车、草稿和快照保持。
- 明确退出、会话过期、401 清理或 customer ID 改变：本地未提交购物车/复购草稿被清除。
- 服务端已提交订单、收藏、积分、任务和游戏持久状态不受影响。
- App 更新本身不会无条件清空当前同 owner 会话的草稿。

### 3.4 回滚

可以回退 scoped key 和清理调用，但不建议恢复读取无 owner 的旧 reconnect token。即使前端完全回退，服务端数据也无需回滚；用户可重新进入房间取得新凭证。

## 4. 配置迁移

### 4.1 环境模板

以下字段仍存在，但 `.env.example` 中故意为空：

```text
ADMIN_PASSWORD=
ADMIN_PASSWORD_HASH=
ADMIN_INVITE_CODE=
ADMIN_SECRET=
CUSTOMER_INVITE_CODE=
WECHAT_APP_SECRET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
REDIS_URL=
```

已有 Render/本地真实环境变量不会被仓库模板覆盖。新环境必须单独生成管理/客户邀请码和签名 secret；生产优先配置 `ADMIN_PASSWORD_HASH`。

### 4.2 Render

- production、staging、Oregon 候选继续使用 `plan: free`。
- production 改为 `autoDeploy:false`。
- 不改变区域、服务名、健康检查、域名或费用。
- 代码合并后必须人工执行发布，发布前先完成备份、隔离恢复和 staging 验收。

### 4.3 逻辑 API 备份

运行前显式设置：

```powershell
$env:PRODUCTION_API_ORIGIN = "https://<approved-production-api>"
$env:ADMIN_PASSWORD = "<runtime-admin-password>"
$env:ADMIN_INVITE_CODE = "<runtime-admin-invite>"
backend\.venv\Scripts\python.exe scripts\backup_production_api.py
```

脚本只接受 HTTPS origin；缺任一变量会在网络请求前退出。该逻辑导出仍不能替代 PostgreSQL 物理/逻辑数据库备份。

## 5. 部署顺序

1. 确认候选文件全部进入可审查提交，远端 CI 通过。
2. 保持生产手动发布门，不从脏工作区部署。
3. 在隔离免费 staging 显式配置独立 secrets 和数据库。
4. 执行现有 migration 链到 `20260817_14`；本轮本身没有新 migration。
5. 验证 `/api/health`、`/api/ready`、邀请登录、首页、下单、管理和在线游戏。
6. 在微信 DevTools/体验版执行客户 A → 退出或过期 → 客户 B，确认草稿和重连 token 不串号。
7. 生产备份可恢复后，人工部署后端；随后发布小程序候选。

## 6. 回滚步骤

### 应用回滚

1. 在 Render 手动选择上一个已知良好提交；不要重新开启自动部署。
2. 小程序回退到上一体验版/线上版本。
3. 验证健康、登录、菜单、下单和管理流程。

### 数据库回滚

本轮无需数据库回滚。若部署包含工作区中既有的 `20260817_14` migration，应按该 revision 自身的 downgrade 与备份恢复流程处理，不能把它误认为本轮 activity/storage 改动。

### 配置回滚

- 不建议恢复弱示例秘密或备份脚本默认生产域名。
- 如需临时恢复旧启动命令，应先人工执行 `alembic upgrade head`，再启动 Uvicorn，并保留 production `autoDeploy:false`。

## 7. 验证方法

- 后端 activity：运行 `backend/tests/test_customer_activity_throttle.py`，并执行全量 pytest。
- API/DB：运行 OpenAPI/schema check 和 empty/from-V2 Alembic upgrade/down/up。
- 小程序 storage：运行 `npm run test:session`，其中包含实际 storage mock 行为测试。
- 前端回归：运行 `npm run test:ci` 和 `npm run build:weapp`。
- 发布门：运行 `scripts/check_release_config.py` 和 `scripts/check_secrets.py`。
- 外部验收：必须在独立 staging、微信体验版和真机单独记录；本地通过不能替代。
