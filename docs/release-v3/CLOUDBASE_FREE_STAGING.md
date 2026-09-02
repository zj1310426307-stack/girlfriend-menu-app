# CloudBase 免费 Staging 接入指南

## 目标与边界

当前 Render Free staging 的 HTTP、WebSocket 和 Neon 持久化业务验收已经通过，但 `onrender.com` 共享域名在微信严格域名校验下仍返回 `MINIPROGRAM_DOMAIN_NOT_ALLOWED`。本方案只替换 staging API 的运行入口，继续使用独立 Neon staging 数据库，不迁移生产数据、不修改公开 API，也不启用付费资源。

腾讯云当前提供一个免费体验版 CloudBase 环境，包含每月 3000 资源点；免费环境需要按规则续期。创建前和每次续期都必须确认控制台仍显示免费，禁止切换付费套餐、开启超额按量计费或绑定收费自定义域名。官方价格规则以 [CloudBase 定价页](https://buy.cloud.tencent.com/price/tcb/overview) 为准。

## 已准备的容器入口

`backend/Dockerfile` 使用 Python 3.12.11，安装锁定的运行依赖，并通过 `python serve.py` 启动。该入口复用 Render 已验证的数据库快速准备流程：只在 schema 落后时迁移，只在参考数据缺失时补齐，然后以 Uvicorn 提供服务。`backend/.dockerignore` 排除本地数据库、测试临时目录、虚拟环境和 Secret 文件，避免扩大镜像或上传本地敏感数据。

## 免费环境配置

截至 2026-09-02，已尝试创建免费体验环境 `loveos-staging`（环境 ID：`loveos-staging-d4gchuaw70bdc5234`）。购买页确认配置费用为 0 元、试用期 6 个月、3000 资源点，并明确免费体验版不支持加购资源包或开启按量付费。环境持续显示 `UNAVAILABLE`；费用中心对应订单显示“发货失败已退款”，1 个资源发货失败，折后总价与实付金额均为 0 元。因此本次创建未成功完成，需由腾讯云支持确认失败原因和免费体验资格恢复方式；不得删除重建、开启付费或把本路径记为通过。

1. 在 CloudBase 控制台创建“免费体验版”环境；若页面不是 0 元或要求开启付费，立即停止。
2. 新建云托管服务，构建上下文选择 `backend`，Dockerfile 使用 `backend/Dockerfile`，服务端口为 `80`。
3. 选择最低可用实例规格，并在控制台支持时启用闲置缩容；不要启用保底付费实例。
4. 环境变量沿用隔离 staging：
   - `APP_ENV=staging`
   - `DATABASE_URL` 指向独立 Neon staging，禁止使用生产连接串
   - `UPLOAD_PROVIDER=database`
   - `CUSTOMER_INVITE_CODE`、`ADMIN_INVITE_CODE`、`ADMIN_SECRET`、`ADMIN_PASSWORD_HASH` 使用 staging 专用 Secret
   - 微信真机阶段再配置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`WECHAT_LOGIN_ENABLED=true`
   - `ALLOW_LEGACY_CUSTOMER_HEADER=false`
5. 健康检查路径设置为 `/api/health`。部署后先验证 `/api/health`，再验证 `/api/ready`。

## 小程序切换与回滚

云托管默认公网域名由腾讯提供。先将该 HTTPS Origin 写入 `miniprogram/.env.staging`，重新构建，并在当前 AppID 的 request、socket、uploadFile、downloadFile 合法域名中配置同一主机（socket 使用 `wss`）。默认域名与小程序通信的官方说明见 [CloudBase 公网访问](https://docs.cloudbase.net/run/deploy/networking/public) 和 [服务设置](https://docs.cloudbase.net/run/deploy/service-setting)。

严格域名校验下通过后，依次执行安全 readiness、带邀请码 HTTP/WebSocket 业务验收、微信开发者工具交互与真机验收。若默认域名仍被微信拒绝，不扩大变更范围，停止该路径并评估 `wx.cloud.callContainer` 私有链路；不得用“不校验合法域名”冒充发布通过。

回滚只需把 `miniprogram/.env.staging` 恢复为 Render staging Origin 并重新构建。Neon 数据库保持不变，不需要数据迁移或回写生产。
