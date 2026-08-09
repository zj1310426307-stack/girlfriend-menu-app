# V2.8 Release Candidate 实施报告

版本：`2.8.0-rc.1`
日期：2026-08-09

## 实际完成

- 审计当前代码并建立真实能力矩阵；DeepSeek 未发现产品接口，因此没有补造 AI 页面。
- 客户设备会话、token 哈希、旧标识一次性认领与 token 轮换。
- 订单归属隔离、`/orders/me`、再次点单预览、幂等提交、UTC 时间及状态审计。
- 12 小时管理令牌、HTTP/WS 统一校验、失败延迟和可替换限流器。
- 管理订单游标分页、状态/日期/关键词筛选和显式回退动作。
- local/S3-compatible 图片存储，真实内容/MIME/大小校验、重编码及 EXIF 清理。
- 管理推送指数退避重连；游戏房间会话元数据、状态版本、热状态抽象、TTL 清理和服务端随机。
- 前端三环境集中配置、客户 Bearer token、菜品缓存、共享异步状态和触控区域统一。
- 数据库备份、恢复核验、发布配置检查、候选文件密钥扫描和 CI 门槛。

## 数据库

新增 migration：`20260809_09_v28_release_security.py`。

新增表：

- `customers`
- `order_status_events`

新增字段：

- `orders.desired_at`
- `orders.status_updated_at`
- `orders.idempotency_key`
- `game_rooms.last_activity_at / expires_at / state_version`
- `game_players.room_session_token_hash / last_activity_at / disconnected_at / expires_at`

迁移不删除旧订单、明细、评价或收藏。生产由 Render 启动命令先执行 Alembic；开发/测试仍保留旧 SQLite 的兼容入口。

## API 变化

新增或稳定化：

- `POST /api/customers/session`
- `POST /api/customers/claim-legacy`
- `POST /api/customers/refresh`
- `GET /api/orders/me`
- `POST /api/orders/{id}/repeat-preview`
- `GET /api/admin/orders?status=&cursor=&limit=&keyword=&start_date=&end_date=`
- `POST /api/admin/orders/{id}/rollback`

兼容期接口 `GET /api/orders/my/{customer_id}` 与 `POST /api/orders/repeat/{id}` 已标记 deprecated。新小程序不再使用 `X-Customer-Id`；生产默认拒绝该伪身份路径。

## 环境变量

新增/明确：

- `APP_ENV`
- `CUSTOMER_INVITE_CODE`
- `ALLOW_LEGACY_CUSTOMER_HEADER`
- `ADMIN_TOKEN_VERSION`
- `UPLOAD_PROVIDER`
- `S3_ENDPOINT / S3_REGION / S3_BUCKET`
- `S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY / S3_PUBLIC_BASE_URL`
- `REDIS_URL`（可选）
- `DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT / DB_POOL_RECYCLE`
- 小程序 `TARO_APP_ENV_NAME / TARO_APP_API_ORIGIN`

## 自动验证结果

- `python -m pytest -q`：56 项（最终运行结果以本文件后续更新和交付消息为准）。
- Taro production build：通过。
- 微信开发者工具结构冒烟：通过；使用本地 V2.8 后端签发的真实测试令牌，不依赖尚未部署的生产接口。
- 空 SQLite → head：通过。
- V2.0 revision → head：通过。
- V2.8 downgrade 一级 → upgrade head：通过。
- Python compileall：通过。
- 密钥扫描：通过，覆盖当前 280 个候选文件（最终数量会随提交文件变化）。
- 发布配置检查：通过。
- SQLite 备份恢复：通过，核对菜品、订单、评价、情侣与游戏实际存在表。

## 未完成 / 外部阻断

- 尚未连接真实 S3-compatible bucket 验证上传和 HTTPS 读取。
- 尚未把生产 Neon 备份恢复到隔离临时 PostgreSQL 数据库。
- 尚未执行两台真实手机的订单隔离、游戏断线与席位恢复验收。
- 尚未完成 Render 冷启动、弱网、小屏和系统大字体的完整记录。
- 未执行微信体验版上传或正式发布。

因此当前不满足 `2.8.0` 正式发布条件，只能作为内部体验版 RC。
