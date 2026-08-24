# Continuous Optimization 03 发布说明

- 候选日期：2026-08-24
- 候选分支：`feature/continuous-optimization-03`
- 状态：PR 自有 CI、小程序全量测试/确定性构建/产物完整性与开发者工具普通模式通过；staging 数据库和微信真机待验收

## 本轮亮点

### 迁移风险更早暴露

现有 GitHub Actions backend job 增加 PostgreSQL 18 临时容器，完整覆盖 head 升级、最后一版降级/再升级和 V2 基线升级，同时保留 SQLite。本轮不购买 Neon 分支或其他数据库服务，也不把临时 CI 凭据用于任何外部环境。

### staging 不再靠人工记忆辨别目标

新增只读 readiness 门，只接受独立公共 HTTPS Origin，并拒绝生产复用、重定向、凭据/path/query、直连 IP和本机/内部域名。脚本只读取 health/ready，限制超时和响应大小，日志只输出目标短摘要和组件状态。

微信采用两阶段门：基础设施部署时允许 optional-disabled；真实秘密配置完成后，`--require-wechat` 必须通过才进入小程序构建和真机验收。

### 开发者工具错误不再反复刷屏

旧 production 暂缺 `/bootstrap` 和 `/customers/wechat-session` 时，小程序按 API Origin 记录 6 小时能力冷却；后台启动不再每次重复探测，用户主动登录仍会立即复探。游戏大厅离线降级保留，但同一次请求不再自动重复 502。菜单分类条增加内部轨道，避免把 padding 解释到 `scroll-view`。

自动页面验收现在完整快照并恢复模拟器 storage，且只精确清理旧版遗留的固定哨兵会话。Taro 4.2 文件缓存曾生成引用不存在数字模块的分包，因此候选构建改为确定性无持久化缓存，并增加产物模块完整性门。

## 兼容性

- 业务 HTTP、WebSocket、DTO、token、OpenAPI 和数据库 revision 不变。
- 小程序新增按 Origin 隔离的本地能力冷却键；不改变已有会话、购物车或快照键语义。
- 主包和总包仅小幅增长，未增加依赖；新验收/产物检查脚本只由开发与发布流程显式执行。
- CI 只增加临时测试数据库覆盖，不改变 production/staging 连接策略。

## 验证摘要

- 定向：20 passed。
- 后端：272 passed，11 条既有 warning；Ruff、compileall、5 条 Import Linter 合同通过。
- 合同：OpenAPI/schema current；CI YAML 可解析。
- 小程序：完整 CI、生产构建和产物模块完整性通过；主包 470,867 B，总产物 890,679 B。
- SQLite：empty/down/up/from-V2 migration matrix 通过。
- 运行：真实 `serve.py` health/ready/dynamic-route smoke 通过，动态房间 sentinel 未进入日志。
- 发布门：免费配置和候选密钥扫描通过。
- PR #21：backend、miniprogram、release-safety 和 Vercel Preview Comments 通过；无网页交付物的旧 Vercel Preview 部署仍为红项。
- 微信开发者工具：服务端口与登录正常；普通模式业务错误为 0，原 404/502、`scroll-view` 和分包缺失模块问题均不再出现。自动化模式仍可能触发 DevTools 3.15.2 自身的超时/预加载提示，不等同于真机。

## 运维动作

1. 保留 PR #21，不合并；确认后断开无网页交付物的旧 Vercel Git 集成，消除无关红项。
2. 在 Neon 免费计划中新建独立空 staging 项目，不复制 production 数据；只把新连接串写入 Render staging。
3. 把 staging start command 对齐为 `python serve.py`，手动部署并运行基础 `check_staging_readiness.py`。
4. 配置真实微信秘密并启用登录，运行 `--require-wechat`。
5. 写入 staging Origin，构建微信包并完成开发者工具、体验版与双真机验收。
6. 未经单独授权不合并 PR、不提交审核、不发布 production。

## 尚未发布与已知限制

本说明不代表 Render staging、微信体验版或真机已通过。当前 staging PostgreSQL 认证失败；未创建 Neon staging 项目、未修改云秘密、未部署或修改 production。开发者工具 3.15.2 的自动化服务仍可能报告内部 timeout 或未使用 preload，这不属于业务代码，但自动化回归需保留失败关闭。跨实例订单/评价附属动作严格不丢不重仍需要后续 outbox/effect ledger，房间旧 owner 写入阻断仍需要 lease fencing。
