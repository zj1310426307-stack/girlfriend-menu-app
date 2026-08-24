# LoveOS V3 部署与回滚

## 发布顺序

1. 从 `render.staging.yaml` 创建独立服务，保持 `autoDeploy=false`；不得把生产 Blueprint 改名后复用。
2. 在空白、非生产克隆的隔离 staging 数据库执行 `alembic upgrade head`，确认 head 为 `20260817_14`。
3. 部署后端，先保持 `WECHAT_LOGIN_ENABLED=false`；此时 `/api/ready` 显示 `wechat_login.status=optional-disabled`。
4. 在 Render Secret 中配置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`。AppSecret 不得进入 Git、小程序源码、构建变量或日志。
5. 配置管理凭据。推荐在本机执行 `python scripts/hash_admin_password.py`，将结果保存为 `ADMIN_PASSWORD_HASH`；兼容期也可保留 `ADMIN_PASSWORD`。
6. 将 `WECHAT_LOGIN_ENABLED=true`，确认 `/api/ready` 的总状态和 `wechat_login.status` 都为 `ready`。
7. 把已核验的 staging HTTPS Origin 写入 `miniprogram/.env.staging`，执行 `npm run build:weapp:staging`；该构建会拒绝生产 API。
8. 完成 staging 新用户、存量用户原地绑定、换机恢复、管理登录、点单和 WebSocket 冒烟。
9. 再上传小程序开发版本并生成真机预览；体验通过后才设置体验版、提交审核或发布。

## 分阶段发布兼容门

`3.0.0` 客户端在微信 session 接口不存在或暂不可用时，可用旧 `/api/customers/recover` 完成邀请码登录；首页 bootstrap 不可用时也会回退旧读取接口。这是为了避免发布窗口中的用户锁死，不用于替代 V3 后端部署。真实微信身份绑定、换机恢复和首屏聚合仍必须在后端迁移至 `20260817_14`、`/api/ready` 显示微信登录 ready 后验收。

## Render 关键配置

staging 必须使用 `APP_ENV=staging`、独立 `DATABASE_URL` 和 `render.staging.yaml`；生产才使用 `APP_ENV=production` 与 `render.yaml`。两者都必须配置各自的 `CUSTOMER_INVITE_CODE`、`ADMIN_INVITE_CODE`、`ADMIN_SECRET`、`UPLOAD_PROVIDER=database|s3` 和微信三项配置，禁止复制生产数据库连接串或业务数据到 staging。

生产、staging 与 Oregon 候选全部固定为免费计划，并使用同一个启动入口：

```text
plan: free
startCommand: python serve.py
```

`serve.py` 在一个 Python 进程内执行免费启动快路径，再启动 Uvicorn。它先用一条查询检查 Alembic head 和参考数据计数；数据库已经就绪时不导入 Alembic、不执行六组种子。首次部署、schema 变化或参考数据不完整时才执行迁移、幂等种子和二次验证。`APP_ENV=production|staging` 时，Uvicorn 生命周期本身不自动建表或种子；本地开发继续自动建表和种子。`release.py` 仅保留为人工修复入口。

当前 Singapore 服务不能原地改 region。若决定让 API 与 Oregon 数据库同区，应在 staging 通过后用 `render.production-oregon.yaml` 新建免费、手动服务并切流，不能覆盖旧服务。详细门槛与回滚见 [免费托管启动计划](performance-rollout-plan.md)。本轮禁止 Starter、付费保活或其他新增费用方案。

Render edge 已承担反向代理、TLS 和公网入口；不额外引入 Nginx。`REDIS_URL` 在单实例下可选；扩展到多实例前必须先完成 Redis/后台任务所有权复审。订单附属动作的跨实例严格不丢不重仍需要后续 transactional outbox / effect ledger，本轮缓存和部署调整不改变这一限制。

## 管理账号迁移

第一次成功的兼容管理登录会创建数据库 `admin` 账号并保存 scrypt 散列。之后以数据库散列验证。需要轮换时，先更新 Render 的 `ADMIN_PASSWORD_HASH`，再用新密码和正确管理邀请码登录一次；只有全部认证因素和账号状态均通过才会写入新 verifier，审计结果为 `SUCCESS_CONFIG_ROTATION`。确认后应移除旧的明文兼容变量。

## 回滚

优先使用前滚修复或回滚应用代码但保留数据库 head。旧应用会忽略新增表，这是风险最低方案。

只有确认尚未产生需要保留的微信绑定和管理审计数据时，才可在备份后执行：

```text
alembic downgrade 20260817_13
```

该操作只删除 `wx_users`、`admin_accounts`、`admin_auth_events`，不会删除 `customers`、`customer_sessions`、订单、积分或游戏历史，但会失去微信绑定和管理登录审计。因此生产环境默认禁止无备份降级。

前端回滚为重新上传上一稳定小程序版本；不要删除用户本地 `gf_customer_id`，它仍是旧身份恢复桥梁。
