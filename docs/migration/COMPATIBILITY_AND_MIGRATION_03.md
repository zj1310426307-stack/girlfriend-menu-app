# Continuous Optimization 03 兼容与迁移说明

- 日期：2026-08-24
- 范围：PostgreSQL CI 迁移门、staging 只读 readiness 工具
- 数据库 revision：保持 `20260817_14`

## 1. 兼容结论

| 边界 | 结论 | 说明 |
| --- | --- | --- |
| 业务 HTTP/OpenAPI | 完全兼容 | 无路由、DTO、状态码或 schema 快照变化 |
| `/api/health`、`/api/ready` | 无服务端变化 | 新脚本只消费既有隐藏运维端点 |
| WebSocket | 完全兼容 | 路由、envelope、重连和结算行为不变 |
| 数据库 | 完全兼容 | 无表、列、索引、约束、数据回填或新 revision |
| 小程序 | 完全兼容 | 源码、页面、分包、storage 和生产包体不变 |
| CI | 覆盖增强 | backend job 增加临时 PostgreSQL 18 service，SQLite 矩阵保留 |
| 运维 | 加法兼容 | 新增显式调用的只读 staging 门，不进入应用运行时 |

## 2. PostgreSQL CI 路径

GitHub Actions backend job 使用 job 生命周期内的一次性 `postgres:18-alpine` service。它不连接 Neon、Render 或生产数据库，也不保存业务数据。CI 顺序为：

1. 空库 `upgrade head`。
2. `downgrade -1` 后再次 `upgrade head`。
3. `downgrade base` 清回空基线。
4. `upgrade 20260808_01` 后再 `upgrade head`，模拟 V2 基线升级。

现有两个 SQLite 文件矩阵继续执行。本轮本机没有 Docker/PostgreSQL 服务，候选未推送，故 PostgreSQL 步骤目前是“workflow 配置与源码合同通过”，不是“远端迁移已通过”。只有远端 backend job 绿灯后才能关闭 `CI-001`。

## 3. staging Origin 安全边界

`check_staging_readiness.py` 要求显式 `STAGING_API_ORIGIN`，并在网络前拒绝：

- 空值、HTTP、非默认 HTTPS 端口；
- 用户名/密码、额外 path、query 或 fragment；
- 生产 `.env.production` 中的 API Origin；
- localhost、直连 IP、`.local` 或 `.internal` 命名目标。

HTTP 重定向被拒绝，每个请求最多读取 64 KiB，超时只能设置为 0–60 秒。错误输出不包含原始 URL、响应正文或网络异常详情；成功输出只含目标 SHA-256 短摘要与组件状态。

## 4. readiness 判定

脚本只执行两个 GET：`/api/health` 与 `/api/ready`。必须满足：

- health 标识为 `girlfriend-menu-api` 且状态 ok；
- 顶层 ready，database 为 PostgreSQL；
- storage ready 且 provider 为 database 或 s3；
- authentication ready 且 missing 为空；
- Redis 为 ready 或 optional-disabled；
- 默认模式微信可为 ready 或 optional-disabled；`--require-wechat` 只接受 ready。

该门不会创建或修改客户、订单、评价、图片或房间，不代替写路径/WebSocket/真机验收。

## 5. 发布顺序

1. 推送候选并确认远端 PostgreSQL/SQLite CI 绿灯。
2. 创建独立免费 staging service 和空白 staging 数据库，禁止复制生产数据。
3. 以微信关闭模式部署，配置独立认证和持久存储，运行基础只读门。
4. 配置真实微信秘密并启用登录，再运行 `--require-wechat`。
5. 写入已核验 Origin，生成 staging 小程序构建并完成体验版/真机验收。
6. 生产发布仍需单独备份、批准和手工部署。

## 6. 回滚

- workflow 回滚只需移除 PostgreSQL service 与六条迁移命令；CI 临时库随 job 自动销毁。
- staging 工具回滚只需删除脚本与测试；无数据库 downgrade、数据恢复或客户端回滚。
- 不建议因远端 PostgreSQL 失败而删除门禁；应修复 revision 方言问题并保留 SQLite 双兼容。

## 7. 外部未验证项

Render 登录、独立 staging 创建、PostgreSQL job 实际执行、hosted readiness、微信 DevTools/体验版/真机、双设备 WebSocket、生产备份恢复均未完成。本轮未使用付费服务、未推送、未修改生产数据。
