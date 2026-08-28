# 微信小程序 V3 发布清单

## 代码与配置

- [x] 小程序使用 `Taro.login`/`wx.login` 获取一次性 code。
- [x] code 只发送后端；后端调用官方 code2Session。
- [x] AppSecret 不在小程序、OpenAPI、日志和 Git 中。
- [x] 新用户邀请码、存量账号原地绑定、换机恢复均有自动化测试。
- [x] 小程序生产构建通过，主包 0.465 MiB，总包 0.834 MiB。
- [x] staging 构建默认无 API 地址并拒绝生产 Origin，未完成隔离服务核对时会失败关闭。
- [x] 独立 `render.staging.yaml` 使用 staging 环境、关闭自动部署并默认关闭微信登录。
- [x] staging 只读门拒绝生产/非 HTTPS/本机目标，并验证 PostgreSQL、持久存储和认证 readiness。
- [x] GitHub Actions 已配置 PostgreSQL 18 临时迁移矩阵；候选 `ed8f2dc` 的远端 backend job 已通过。
- [ ] 基础 staging 只读门在微信关闭状态通过。
- [ ] Render staging 配置真实 AppID/AppSecret 并启用开关。
- [ ] `check_staging_readiness.py --require-wechat` 在 staging 通过。

## 微信公众平台

- [ ] request 合法域名为生产 HTTPS API Origin，不含 `/api` 路径。
- [ ] socket 合法域名为对应 WSS Origin。
- [ ] uploadFile / downloadFile 域名与真实存储路径一致。
- [ ] 隐私保护指引声明登录标识和业务数据用途。
- [ ] 用户隐私、服务类目、名称、图标、截图和版本说明复核完成。
- [ ] 体验成员覆盖新用户、存量用户、换机用户和管理员。

## 验收场景

- [ ] 首次进入：微信登录后要求邀请码，错误邀请码不可建用户。
- [ ] 存量设备：后台绑定后 `customer_id` 不变，历史订单/积分/游戏仍在。
- [ ] 新手机：无需旧设备 ID 即可恢复同一 `customer_id`。
- [ ] 旧手机：绑定不会使现有会话失效。
- [ ] 首页：推荐、恋爱值、今日任务、最近订单正常；菜单缓存命中快速打开。
- [ ] 管理端：数据库散列登录成功，错误登录写审计且不泄露凭据。
- [ ] 管理端并发：两台设备基于同一旧状态操作时，后到请求提示刷新且不追加错误审计或副作用。
- [ ] 写入故障恢复：订单状态、撤回或评价的通知、任务、积分、记忆、广播模拟失败时，主结果仍如实成功并可安全重试。
- [ ] 网络异常：code 失效、限流和微信服务不可用提示可理解。
- [ ] 订单、图片、五个一级入口、游戏和 WebSocket 冒烟通过。

## 外部操作状态

- [x] 微信小程序 `3.0.0` 已上传为开发版本。
- [ ] 有权威页面状态证明 `3.0.0` 已设为体验版。
- [x] 候选后端已 commit/push 并形成 PR #21。
- [ ] 候选已部署到隔离 staging。
- [ ] 已提交审核。
- [ ] 已正式发布。

2026-08-28 只读核验显示 Neon 免费组织只有一个项目和一个分支，隔离 staging 尚不存在。先创建独立 staging、完成 hosted 与微信真机验收，再设置体验版；生产迁移、提交审核与正式发布均未执行。

官方依据：

- <https://developers.weixin.qq.com/miniprogram/dev/api/open-api/login/wx.login.html>
- <https://developers.weixin.qq.com/miniprogram/dev/server/API/user-login/api_code2session.html>
