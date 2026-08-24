# LoveOS V3 本轮优化执行计划

- 计划日期：2026-08-24
- 轮次：Continuous Optimization 01
- 主题：身份热路径、同设备状态隔离与零付费发布安全
- 依据：`docs/audit/CURRENT_STATE_AUDIT.md`、`docs/audit/OPTIMIZATION_BACKLOG.md`

## 1. 目标

在不改变公开 API、不改变数据库 schema、不引入付费资源的前提下：

1. 让最近活跃客户的认证请求不再为 `last_seen_at` 产生远程数据库写和 commit。
2. 确保同一设备切换客户后，前一客户的购物车、复购草稿和游戏恢复秘密不可被后一客户读取或使用。
3. 把生产发布改为明确的人工门，清除仓库中的已知弱默认凭据。
4. 形成可复现的审计、测试、兼容、回滚和发布证据。

## 2. 实施范围

### 工作流 A：认证热路径

- 在 `customer_service` 增加固定服务端 last-seen 写入窗口（初始 5 分钟）。
- 认证仍逐请求查询 session，并先检查 customer active、session revoked 和 expires。
- 最近活跃 session 直接返回，不修改 ORM，不 commit。
- 超过窗口时用带 cutoff 条件的更新触碰 session；只有该更新取得 ownership 时才同步触碰 customer 并 commit。
- 保留 `update_last_seen=False` 的 WebSocket/延迟敏感调用语义。
- 暂不移除 `ensure_user`，避免把兼容身份桥与本轮性能修复混合。

### 工作流 B：小程序私有状态隔离

- 新增无 API 依赖的 session-owned storage 工具。
- 游戏重连 key 从 `roomCode` 调整为 `customerId + roomCode`。
- 不信任旧版无 owner 的 reconnect key；合法当前用户仍可通过已认证状态接口恢复并重新签发 token。
- `clearCustomerSession()` 和 session owner 变化时清理：
  - 购物车；
  - 复购草稿；
  - 新旧 reconnect key；
  - 遗留 `gf_room_session_*` secret；
  - 已有客户首页/Tab 快照。
- 停止在 WebSocket 消息处理中持久化未被消费的 room-session secret。
- 清理采用 best effort、逐 key 隔离，确保某一个 storage 异常不阻断其余登出清理。

### 工作流 C：发布安全

- 生产 `render.yaml` 改为 `autoDeploy:false`，继续保持 `plan: free`。
- `.env.example` 的密码、邀请码和签名密钥值全部留空，并写清生成/配置方法。
- `backup_production_api.py` 要求 API origin、管理员密码和管理员邀请码全部显式提供。
- `check_release_config.py` 增加生产手动发布门和已知弱默认检查。
- 同步本轮触及的 README/发布材料，不把未提交或未外部验收的候选写成已发布。

### 工作流 D：测试与交付

- 后端新增 last-seen 节流回归：热 session 无写、过窗触碰一次、stale 并发视图不重复覆盖、失效语义不变。
- 小程序新增实际执行 storage mock 的行为测试；保留现有源码合同测试作为结构门。
- 运行定向门后运行全量后端、小程序 CI、微信构建、迁移和发布安全检查。
- 生成兼容/迁移、验证报告和发布说明。

## 3. 明确不做

- 不部署 production 或 staging，不调用外部数据库/微信/S3，不创建任何付费资源。
- 不在本轮实现 outbox/effect ledger、跨实例 lease fencing 或后台任务全局 ownership。
- 不改变 HTTP 路由、DTO、WebSocket 公共 envelope、token 格式或 OpenAPI 快照。
- 不新增/修改表、列、索引或 Alembic revision。
- 不顺带重构大型模块、不移除兼容 header/legacy recovery、不引入生成式 API 客户端。
- 不把本地模拟器结果替代微信真机、体验版或 PostgreSQL staging 验收。

## 4. 兼容策略

- last-seen 是观测字段，5 分钟内延迟写入不影响认证、撤销、过期和业务授权。
- 旧 reconnect token 因缺少 owner 不能安全自动归属，将被视为不可信；当前合法客户可通过 bearer 状态读取恢复房间并重新登记 token。
- 购物车和复购草稿是设备本地临时数据；会话清理/owner 切换时删除是安全边界修正，不迁移到新客户。
- `render.yaml` 只改变部署触发方式，不改变运行规格、区域、域名或费用。
- 环境模板值留空不影响已部署环境变量；新环境必须显式配置。

## 5. 回滚策略

| 改动 | 回滚方式 | 数据影响 |
| --- | --- | --- |
| last-seen 节流 | 回退相关 service 提交，恢复逐请求 touch | 无 schema/data 迁移；仅写频率变化 |
| scoped reconnect key | 回退前端代码；不建议恢复读取无 owner legacy secret | 当前会话可重新签发，不修改服务端房间 |
| 会话私有数据清理 | 回退清理调用 | 已清除的本地草稿不可恢复，但服务端订单/游戏数据不受影响 |
| 停止 room-session 落盘 | 回退 message handler | 该值当前没有读取方，无业务数据丢失 |
| autoDeploy false | 在完成备份/验收后手工改回（不推荐） | 无运行数据变化 |
| 空白 env 示例 | 回退文档模板（不推荐恢复弱值） | 已部署 secrets 不受影响 |

## 6. 验收标准

### 性能与正确性

- 热 session 连续认证时，`customers`/`customer_sessions` 不产生持久化 UPDATE。
- stale session 首次认证更新 last-seen，紧随其后的认证不再写；并发 stale 视图不能用第二个时间覆盖第一个窗口。
- revoked、expired、inactive 和 legacy bridge 语义继续通过现有测试。
- bootstrap、订单和游戏公开响应不变化，OpenAPI `--check` 通过。

### 隐私与本地状态

- 客户 A 保存 cart/draft/reconnect 后，清会话或保存客户 B，会话私有数据为空。
- B 无法取得 A 的 reconnect token；同一客户和房间可以正常取得新 key token。
- 旧 `gf_game_reconnect_ROOM`、新前缀和 `gf_room_session_ROOM` 均可清理。
- 连续清理幂等；单个 remove 失败不阻断后续 key；公共菜品缓存保留。

### 发布安全

- production/staging/Oregon Blueprint 全部保持免费计划并关闭自动部署。
- 示例和备份工具不含 `admin123`、`love2026` 或可直接使用的 placeholder secret。
- 缺 origin/password/invite 任一变量时逻辑备份脚本在网络请求前失败。
- 发布配置和密钥扫描门通过。

### 回归门

- 后端全量 pytest、Ruff、Import Linter、compileall、schema/OpenAPI check 通过。
- Alembic empty upgrade、down/up、from-V2 upgrade 通过。
- 小程序 `npm run test:ci` 和 `npm run build:weapp` 通过；包体不突破微信限制和现有预算。
- 启动 smoke 与 `/api/health` 通过。

## 7. 发布门

本轮完成代码和本地验证不等于允许生产发布。进入生产前仍需：

1. 形成完整可审查提交并由远端 CI 验证。
2. 在隔离免费 staging 上配置独立 secrets 和数据库，完成备份/恢复与迁移验证。
3. 微信 DevTools、体验版和至少两台真机完成 A→退出/过期→B、首页、下单、管理和在线游戏核心路径。
4. 人工确认生产备份可恢复后，再手动部署；出现异常按兼容/迁移文档回滚。

## 8. 执行结果

本计划的本地实施范围已于 2026-08-24 完成：工作流 A/B/C/D 均已落地，236 项后端测试、小程序生产构建与 CI、迁移、启动和发布门通过。详细证据见验证报告。

外部发布门尚未完成，因此本轮状态是“本地候选完成、staging/真机/production 待验收”，不是“已上线”。
