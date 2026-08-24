# LoveOS V3 优化 Backlog

- 更新日期：2026-08-24
- 优先级口径：P0 发布/安全阻断；P1 直接影响核心体验或数据边界；P2 重要但可排期；P3 长期治理
- 状态口径：`本轮`、`待排期`、`外部验收`、`已具备基础`

| ID | 优先级 | 状态 | 问题位置 | 表现 / 根因 | 影响 | 建议 | API / DB | 验收标准 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-001 | P0 | 已完成（本地） | Git 工作区 | 审计时有 56 个 tracked 改动、30 个 untracked；启动入口、迁移和配置未形成完整提交 | 当前目录不能作为可复现发布物，漏文件会启动失败或 schema 漂移 | 新建安全分支、冻结清单；仅从完整提交和 CI 候选发布 | 无 | 已建立独立分支并按后端/前端/发布/文档拆分提交；仍须远端 CI 后才可发布 |
| PERF-001 | P1 | 已完成 | `customer_service.authenticate` | 每个 bearer 请求刷新两张表并 commit | 首页/Tab 读取增加远程 DB 写、WAL 和失败面 | 5 分钟 last-seen 节流 + 条件更新 | API 不变；DB 不变 | 行为测试证明热 session 零 UPDATE/commit；过窗只触碰一次；失效语义不变 |
| PRIV-001 | P1 | 已完成 | `customer.js`、`cart.js`、`gameRecovery.js` | 私有本地数据无 owner 或不随会话清理 | 同设备换账号可看到旧购物车/草稿，甚至恢复前账号游戏 | owner-scoped reconnect key；owner 切换/清会话清理；停止保存未用 secret | API/DB 不变；本地 key 调整 | storage 行为测试证明 A/B 隔离、旧 key 清理、公共缓存保留和幂等 |
| REL-002 | P1 | 已完成 | `render.yaml`、`serve.py` | 生产 autoDeploy 会触发启动时自动迁移 | 代码合并可能绕过备份和 staging 门直接迁移生产 | 生产 `autoDeploy:false`；静态检查强制手动发布 | 无 | 三套 Blueprint 均为 free 且关闭自动部署；发布门通过 |
| SEC-001 | P1 | 已完成 | `.env.example`、`backup_production_api.py` | 模板和脚本含已知弱默认 | 复制模板或误跑脚本可能使用公开凭据/错误目标 | 清空秘密示例；origin/密码/邀请码全部显式输入；发布门拒绝弱值 | 无 | 弱默认已移除；缺配置/HTTP origin 均在网络前失败；密钥扫描通过 |
| READY-001 | P1 | 待排期 | `/api/ready` | readiness 不检查客户/管理员认证配置 | 服务显示 ready 但双方无法登录 | 增加不泄密 auth readiness | 响应字段会扩展；DB 不变 | 缺关键凭据时非 ready，响应不含秘密 |
| OBS-001 | P1 | 待排期 | HTTP/cache/game 日志 | 原始 path、cache key、房间码进入日志 | 房间码或客户标识泄露 | 路由模板或不可逆短哈希；sentinel 测试 | 无 | 日志中不出现测试 sentinel 原文 |
| DATA-001 | P1 | 待排期 | 订单/评价副作用 | 主事务后积分、通知、记忆和广播仅 best effort | 进程崩溃会永久缺副作用；跨实例广播缺失 | durable outbox/effect ledger + 幂等消费者 | 需内部 API/DB 迁移 | 故障注入后最终一次且仅一次完成可持久副作用 |
| GAME-001 | P1 | 待排期 | room lease/state store | `lease_epoch` 未进入状态写 fencing | 旧实例可能覆盖新 owner 状态 | owner+epoch 传递并条件写 | 内部协议/DB 语义变更 | 接管后旧 epoch 写入被拒绝 |
| DATA-002 | P1 | 待排期 | free runtime seed 判断 | 仅比较固定表计数 | 内容更新但数量不变时线上种子不更新 | 持久 `REFERENCE_DATA_VERSION` | 需要小型 DB 迁移 | 版本变化准确触发一次 seed |
| CI-001 | P1 | 待排期 | GitHub Actions | 迁移仅验证 SQLite | PostgreSQL DDL、锁、约束风险未被 CI 捕获 | 免费 Actions PostgreSQL service 迁移门 | 无公开 API；测试 DB | upgrade/down/up 与 from-V2 在 PG 通过 |
| WX-001 | P2 | 待排期 | 首页微信绑定 | 能力关闭时每次启动仍发必败请求 | 免费冷启动多一条 503 请求 | 404/405/501/503 持久能力冷却；显式登录可绕过 | API 不变 | 冷却期启动只发 bootstrap，不发绑定探测 |
| QUERY-001 | P2 | 待排期 | order relationships/love score | 无用 selectin；历史积分全量加载 | 数据增长后首页和订单列表退化 | 精确 projection/SQL 聚合，补查询预算 | API 不变；可能补索引迁移 | 结果等价，查询数和扫描行有预算 |
| UPLOAD-001 | P2 | 待排期 | upload/storage | async 路由内同步 Pillow/provider；无像素上限 | 事件循环阻塞、压缩炸弹内存风险 | threadpool、typed error、像素/边长上限 | API 状态语义不变 | 大图快速拒绝；并发 health 不被阻塞 |
| AUTH-001 | P2 | 待排期 | admin token | 停用账号不立即撤销已签 token | 最长约 12 小时残余权限 | token 校验绑定账号状态/版本 | token 验证内部变化 | 停用后下一请求立即 401/403 |
| GAME-002 | P2 | 待排期 | background jobs | 每实例运行维护/通知任务，缺全局 ownership | 多实例重复扫描、通知或 settlement 竞争 | DB lease/唯一约束/skip locked | 需 DB 迁移 | 两实例只执行一次业务效果 |
| GAME-003 | P2 | 待排期 | room detail | 持房间码即可读取稳定玩家标识 | 房间码泄露后可枚举成员 | bearer/room member 认证，响应最小化 | 公开 API 行为变更 | 非成员 403；兼容迁移说明完成 |
| FE-001 | P2 | 待排期 | 首页生命周期 | 返回首页后不主动刷新或标脏 | 下单/任务后摘要可能旧到页面重建 | useDidShow + 脏标记/冷却刷新 | 无 | 返回后按冷却刷新且不请求风暴 |
| FE-002 | P2 | 待排期 | gomoku/dice-online | 仅 React state 防重复创建 | 同帧双击可能双 POST | 同步 ref 锁，对齐其他游戏 | 无 | 连续双击只发一次创建请求 |
| FE-003 | P2 | 待排期 | 手写 API wrapper | 529 行 wrapper 依靠人工同步 | 字段/类型漂移难发现 | 从 OpenAPI 生成最小类型/客户端或 schema 门 | 构建链变化 | 合同漂移能在 CI 失败 |
| A11Y-001 | P2 | 待排期 | View+onClick 控件 | role/aria/disabled 语义不足 | 读屏和辅助触控体验不可靠 | 语义 Button 或补 role/aria | 无 | 核心流程 a11y 自动/人工检查通过 |
| IMG-001 | P2 | 待排期 | cart/admin/detail 图片 | 限宽、lazy、失败回退不一致 | 移动流量和首屏解码开销 | 统一图片组件/参数预算 | 无 | 核心图片全部有尺寸、lazy 策略和回退 |
| BACKUP-001 | P2 | 待排期 | backup scripts | 数据库备份可静默回退 SQLite；API 备份不覆盖 V3 全数据 | 可能“备份成功”但目标错误 | production fail-closed、目标摘要和恢复演练 | 无 | 错目标无法运行；隔离恢复可验证 |
| DOC-001 | P2 | 已完成（本轮范围） | README/发布文档 | 启动入口、候选状态存在漂移 | 运维误操作和错误验收 | 同步 `serve.py`、空白 secrets、手动发布门、兼容/验证/回滚说明 | 无 | README 与六份强制交付文档已同步；历史 Procfile 漂移仍列后续治理 |
| MAINT-001 | P3 | 待排期 | 大型模块 | manager/models/schemas/order service/API wrapper 过大 | 修改冲突和认知负担 | 按稳定边界小步拆分 | 应保持 API/DB | 每次拆分有架构契约与回归 |
| SUPPLY-001 | P3 | 待排期 | Python/Actions | 无传递依赖 hash 锁；Actions 使用浮动 major tag | 构建可复现和供应链风险 | 生成锁/约束；固定 action SHA | 无 | 冷环境安装可复现，更新由 Dependabot 管理 |
| REPO-001 | P3 | 待排期 | 仓库文本 | 无 `.gitattributes` | LF/CRLF 噪声 diff | 固定源码/配置 LF | 无 | clean checkout 不产生换行 diff |

## 本轮完成定义

只有在以下条件全部满足后，表中标记“本轮”的条目才可更新为完成：

1. 代码、行为测试、兼容/迁移文档、验证报告和发布说明全部存在。
2. 定向测试、后端全量测试、小程序 CI、微信构建、迁移链和发布安全门全部通过。
3. 没有新增付费服务、没有生产部署、没有公开 API 或数据库结构变化。
4. 外部 staging/真机未执行时必须明确标为待验收，不能写成已通过。
