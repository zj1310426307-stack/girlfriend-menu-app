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
- [x] 基础 staging 只读门在微信关闭状态通过。
- [x] Render staging 配置真实 AppID/AppSecret 并启用开关。
- [x] `check_staging_readiness.py --require-wechat` 在 staging 通过。

## 微信公众平台

- [x] 当前 AppID 后台列表的 request、socket、uploadFile、downloadFile 均包含 staging Origin。
- [x] 严格域名校验下 staging `/api/health` 与真实登录/bootstrap 请求成功。
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

Hosted 自动验收已通过客户会话/存量恢复、管理登录、菜单收藏、订单/评价/撤回、持久图片、管理 WebSocket 和双客户端游戏 WebSocket/重连。开发者工具随后通过真实微信 code、OpenID 绑定/恢复及五个一级入口验收；发布负责人最终确认真机弱网、后台恢复、身份恢复和双设备在线重连全部正常。各证据按其来源分别记录，不互相冒充。

## 外部操作状态

- [x] 微信小程序 `3.0.0` 当前候选已上传为开发版本。
- [x] 2026-09-03 最新上传的 `3.0.0` 开发快照已再次成为体验版；公众平台权威显示提交时间 15:34:34、项目备注 `LoveOS V3 staging real WeChat login acceptance`。
- [x] 候选后端已 commit/push 并形成 PR #21。
- [x] 候选已部署到隔离 staging。
- [ ] 已提交审核。
- [ ] 已正式发布。

2026-08-28 已创建独立 Neon Free staging 项目和 Render Free staging 服务，基础只读门与 hosted 业务写链路通过。真实微信凭据、OpenID 绑定、开发工具交互和真机验收仍待完成；生产迁移、提交审核与正式发布均未执行。

2026-09-02 已对当前 PR #21 候选重新执行小程序测试、staging 构建和产物完整性检查，并通过微信开发者工具上传 `3.0.0`。上传结果为总包 849.9 KB、主包 444.4 KB；微信公众平台显示最新提交时间为 2026-09-02 15:31:54，版本带“体验版”标记，操作菜单为“取消体验”。这证明当前上传构建已成为体验版，但不替代严格域名、真实微信登录、OpenID 绑定和真机业务验收；未提交审核、未正式发布。

2026-09-03 staging 的真实微信配置与严格 readiness 已通过。开发者工具使用真实 `wx.login` code 完成首次邀请码绑定与无邀请码恢复，同一客户身份保持不变，两轮 bootstrap 均为 200；已认证首页冷启动无异常。随后再次上传 `3.0.0` 开发版本成功，总包 849.9 KB、主包 444.4 KB。公众平台已权威确认本次 15:34:34 上传快照为体验版。发布负责人进一步确认真机核心业务、切后台恢复、网络切换/断线重连、双设备在线游戏及清除本地会话后的无邀请码历史恢复均正常。生产 API 逻辑备份、PostgreSQL 自定义格式备份、SHA-256、行数清单与本地隔离恢复均已通过；V3 生产迁移、提交审核与正式发布仍未完成。

官方依据：

- <https://developers.weixin.qq.com/miniprogram/dev/api/open-api/login/wx.login.html>
- <https://developers.weixin.qq.com/miniprogram/dev/server/API/user-login/api_code2session.html>
