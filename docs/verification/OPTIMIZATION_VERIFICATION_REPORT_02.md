# Continuous Optimization 02 验证报告

- 日期：2026-08-24
- 分支：`feature/continuous-optimization-02`
- 结论：本地候选通过；隔离 staging、微信真机和 production 未执行

## 1. 需求与实现对应

| 需求 | 实现 | 结果 |
| --- | --- | --- |
| 服务不可登录时不能显示 ready | service 层 authentication readiness + 顶层聚合 | PASS |
| readiness 不泄露秘密 | 只返回状态和安全配置项名称 | PASS |
| 管理 hash 损坏可见 | verifier 结构检查与独立 blocker | PASS |
| 动态 HTTP path 不进日志 | route template；未知路由 `/unmatched` | PASS |
| 请求 ID/key/room 不进日志 | 随机 HMAC 进程内短引用 | PASS |
| 异常消息不夹带输入 | 隐私敏感位置只记录 `error_type` | PASS |
| Uvicorn 不重复打印原始 URL | 标准 `serve.py` 设置 `access_log=False` | PASS |

## 2. 自动化测试

新增 16 项专项测试：

- readiness 10 项：缺失配置、已有/无管理员、禁用账号、托管环境邀请码分离、无效环境/数据库 hash、数据库异常和顶层聚合。
- logging privacy 6 项：短引用稳定性、动态/未知路由、Redis 故障、游戏状态故障和目标模块源码合同。

后端全量：

- `pytest -q`：252 passed。
- 警告：11 条 SQLite Python 3.12 默认 datetime adapter deprecation，来自既有 customer session migration 测试；无失败。
- 中断后最后一次完整运行再次通过，证明结果不依赖前一次测试进程状态。

质量与架构门：

- Ruff：PASS。
- `compileall`：PASS。
- Import Linter：129 files、416 dependencies、5 contracts kept、0 broken。
- OpenAPI snapshot：current。
- PostgreSQL schema snapshot：current。

## 3. Readiness 行为

专项测试确认：

- 无数据库管理员且无 password/hash：`ADMIN_PASSWORD_OR_HASH`。
- 已有启用管理员和有效数据库 verifier：无需 bootstrap password，状态 ready。
- 禁用管理员：`ADMIN_ACCOUNT_ACTIVE`。
- 无效环境 hash：`ADMIN_PASSWORD_HASH`；即使同时设置明文 password 也阻止，因为登录实现优先读取 hash。
- 无效数据库 verifier：`ADMIN_ACCOUNT_PASSWORD_HASH`。
- 托管环境共用邀请：`AUTH_INVITE_SEPARATION`。
- 管理账号表查询失败：`ADMIN_ACCOUNT_STORE`，响应不包含数据库错误文本。

实际本地进程使用独立 SQLite 与显式测试 secrets：

- `/api/health`：200，`status=ok`。
- `/api/ready`：200，总状态 ready。
- `authentication.status=ready`，`missing=[]`。
- `storage.status=ready`；`wechat_login.status=optional-disabled`；database 为 sqlite。

## 4. 日志隐私

自动化 sentinel 覆盖确认日志不出现：

- 动态房间 URL；
- 客户端自定义 `X-Request-Id`；
- Redis cache key；
- 房间码；
- 人工注入的异常消息。

真实 `serve.py` 进程访问动态路径后，应用日志仅出现类似：

```text
request request_ref=request:<short-ref> method=GET route=/api/games/rooms/{room_code} status=404 duration_ms=<value>
```

Uvicorn 没有输出原始动态 URL access line。首次 smoke 暴露该默认日志后已补修并重新验收，未把失败结果当作通过。

## 5. 小程序回归与包体

本轮没有修改小程序，但仍执行完整交付门：

- `npm run test:ci`：全部通过，覆盖横屏斗地主、游戏长时运行、socket lifecycle、session/storage、V3 架构、核心产品流、首页与 Tab 启动合同。
- `npm run build:weapp`：Taro/WeApp 生产构建成功。

构建产物保持上一轮大小：

| 范围 | 文件数 | 大小 |
| --- | ---: | ---: |
| 主包 | 57 | 469,038 B |
| 总产物 | 182 | 888,826 B |

本轮没有声称真实微信网络首屏进一步提速；构建和启动合同的意义是证明后端改造没有引入前端回归。

## 6. 数据库迁移

使用两个显式临时 SQLite 文件执行并清理：

1. 空库 `upgrade head` 到 `20260817_14`：PASS。
2. 同库 `downgrade -1` 到 `20260817_13`：PASS。
3. 再 `upgrade head`：PASS。
4. 独立库 `upgrade 20260808_01`，再到 head：PASS。

本轮没有新 revision；该矩阵只证明既有迁移链未被代码变化破坏。PostgreSQL 方言、锁和恢复仍待隔离 staging。

## 7. 启动与发布安全

- 标准 `serve.py` 在全新独立 SQLite 上完成 migration、reference seed 和 Uvicorn startup。
- health、ready 和动态 404 请求均成功返回预期状态。
- smoke 进程停止后临时数据库已删除。
- `check_release_config.py`：PASS，免费计划与人工发布门保持。
- `check_secrets.py --candidate HEAD`：497 个候选文件扫描通过。
- 未访问外部 PostgreSQL、Redis、微信、S3、Render 或任何付费 API。

## 8. 风险与验证边界

- SQLite datetime adapter 的 11 条弃用警告仍待单独升级处理。
- 日志短引用跨进程/实例不可关联；这是一项隐私属性，也意味着长期排障必须依赖低基数 metrics/traces，而不是短引用。
- 关闭 Uvicorn access log 后，必须确保应用中间件日志被托管平台采集；本地已验证，Render 尚未验证。
- 管理 hash 格式收紧可能拒绝历史手工拼装值；项目生成的标准历史值兼容，staging 必须在发布前查看 readiness。
- 订单附属动作跨实例严格不丢不重仍需要 durable outbox/effect ledger。
- 游戏接管后的旧实例写 fencing、后台任务全局 ownership 仍未完成。
- 微信体验版、真机弱网、真实微信身份、双设备游戏和 production 备份恢复仍未验证。
