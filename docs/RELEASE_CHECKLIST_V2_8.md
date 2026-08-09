# V2.8 RC 发布验收清单

候选版本：`2.8.0-rc.1`。只有全部阻断项完成后，才允许改为 `2.8.0`。

## 已自动验证

- [x] 真实能力矩阵已完成，未把 DeepSeek 或规划功能伪装为产品能力。
- [x] 后端测试：`56 passed`。
- [x] Alembic 空 SQLite 升级到 head。
- [x] Alembic 从 V2.0 revision `20260808_01` 升级到 head。
- [x] V2.8 migration downgrade 一级后可再次升级。
- [x] 小程序生产构建 `npm run build:weapp` 通过。
- [x] 微信开发者工具 `npm run test:v28` 结构冒烟通过（本地后端签发测试会话）。
- [x] 静态敏感信息扫描与发布配置检查通过。
- [x] SQLite 备份、临时恢复、完整性和关键表行数核对通过。
- [x] 客户令牌只保存哈希；伪造 `X-Customer-Id` 的生产路径被拒绝。
- [x] 订单归属、重复评价、重复提交、合法状态跳转有自动测试。
- [x] 生产启动只依赖 Alembic，不执行 `create_all` 或手写兼容迁移。

## 外部发布阻断项

- [ ] 在 Render 配置全部 S3-compatible 环境变量；`/api/ready` 的 `storage.status` 必须为 `ready`。
- [ ] 实际上传 JPEG/PNG/WebP，并从返回的稳定 HTTPS 地址读取图片。
- [ ] 对 Neon 备份执行一次隔离临时 PostgreSQL 恢复和行数核对。
- [ ] Render 部署后验证 `/api/health` 与 `/api/ready`，记录冷启动表现。
- [ ] 微信后台配置 request/socket/uploadFile/downloadFile 合法域名。
- [ ] 两台真机完成在线房间加入、临时退出、60 秒内恢复原席位和正常结算。
- [ ] iPhone 小屏、Android 常见尺寸、大字体、刘海/底部安全区通过。
- [ ] 弱网下菜单可重试、清单不丢、提交不重复、WebSocket 恢复后重拉数据。
- [ ] 管理令牌到期、退出和 401 自动清理行为在真机通过。

## 用户主流程

- [ ] 清缓存，邀请码建立设备会话。
- [ ] 浏览/筛选/搜索菜单，收藏并加入点菜清单。
- [ ] 修改数量、备注、用餐时间并提交。
- [ ] 关闭重进后从“点菜单”找到订单。
- [ ] 管理员按合法流程更新状态。
- [ ] 完成后评价；再次进入不能重复评价。
- [ ] “再做一次”只生成可编辑预览，不越权复制其他设备订单。

## 权限负向测试

- [ ] 设备 A 的订单不能被设备 B 查看、评价或复制。
- [ ] 无效/过期 customer token 返回 401。
- [ ] 无效/过期 admin token 不能访问 HTTP 与 WebSocket 管理入口。
- [ ] 生产配置下自填 `X-Customer-Id` 不生效。

## 发布决定

当前决定：**NO-GO for `2.8.0`，GO for internal RC testing**。未完成上述外部阻断项前，只能上传为体验版候选，不得声明最终稳定版。
