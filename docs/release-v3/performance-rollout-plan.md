# LoveOS V3 免费托管启动计划

更新日期：2026-08-23
状态：**仓库免费候选已就绪，云端未应用，禁止新增费用**

## 目标与边界

本计划在 Render 免费实例会休眠的前提下，减少醒来后的应用工作、避免客户端请求风暴，并准备免费的 Oregon 同区候选。应用代码无法取消平台休眠，因此不承诺把首次网络响应变成常驻服务水平；复访体验主要依靠按账号隔离的本地先显。

本计划不承诺跨实例附属动作 exactly-once；该能力仍需 transactional outbox / effect ledger。

## 已在仓库完成

- `render.yaml`、`render.staging.yaml`、`render.production-oregon.yaml` 全部固定为 `plan: free`，发布门禁会拒绝 Starter 和 pre-deploy。
- 三个 Blueprint 统一使用 `python serve.py`，在一个进程内准备数据库并启动 Uvicorn。
- 每次唤醒先用一条查询读取 Alembic head 与六组参考数据计数；已就绪时跳过 Alembic 和种子。
- 首次部署、schema 变化或参考数据缺失时，仍会迁移、执行幂等种子并二次验证，失败时不启动 Web 服务。
- 隔离 SQLite 首次准备约 1.388 秒；第二次唤醒快路径约 5.0ms。该数字只说明本地代码路径，不代表 hosted 网络耗时。
- 首页网络超时不再展开旧五接口；四个一级页对成功刷新设置会话内冷却，失败与手动重试不受冷却阻挡。
- `render.production-oregon.yaml` 是新的免费手动候选，不修改现有 Singapore 服务。

## 外部执行门槛

1. 先创建完全隔离的免费 staging 数据库与 Render staging 服务，不复制生产连接串或业务数据。
2. 部署明确的候选提交，确认 `/api/health`、`/api/ready`、Alembic head `20260817_14` 和 `free_runtime_ready` 日志。
3. 让 staging 进入休眠后采集 10 次真实冷唤醒，并完成微信真机登录、菜单、下单、订单状态、评价、图片与 WebSocket 冒烟。
4. 若跨区数据库仍占显著比例，使用 `render.production-oregon.yaml` 新建免费 Oregon 服务；先以临时 Origin 验收，再修改小程序生产 Origin。
5. 新服务稳定观察后才停用旧服务。数据库、域名和旧服务至少保留一个完整回滚窗口。

## 验收阈值

- 微信真机复访：本地内容先出现，后台同步不清空已有页面。
- 首页 bootstrap：无重复并发请求；网络失败不展开五接口，旧后端 404/405/501 仍能兼容降级。
- 普通免费唤醒：日志显示 `schema_changed=false`、`reference_data_seeded=false`，不重复运行迁移与种子。
- Tab 快速往返：冷却期内不重复读取服务端；失败后可以立即重试。
- 所有写操作仍以服务端结果为准，缓存中不保存 bearer，账号切换不串数据。

## 回滚

- `serve.py` 异常：恢复上一稳定启动命令；不要降级数据库 schema。
- Oregon 免费新服务异常：把 Origin 切回 Singapore 旧服务；旧服务未确认稳定前不得删除。
- 客户端缓存异常：清理 `gf_home_snapshot_v31` / `gf_tab_snapshots_v31` 后会自动回到网络权威读取，不影响数据库数据。
- 迁移或种子异常：停止切流，修复后前滚；没有备份和数据影响评估时禁止数据库 downgrade。
