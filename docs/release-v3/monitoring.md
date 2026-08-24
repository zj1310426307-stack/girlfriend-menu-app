# LoveOS V3 监控与告警

## 已有信号

- `/api/health`：进程存活。
- `/api/ready`：数据库、存储、Redis降级状态和微信登录配置状态。
- `X-Request-Id` + 请求日志：method、path、status、duration，不记录 body、token 或 secret。
- OpenTelemetry：显式 opt-in、低基数 allow-list、默认 no-op，不将 exporter 故障传入业务。
- 数据库审计：订单状态事件、游戏事件和管理登录事件。

## 建议告警

| 信号 | 建议阈值 |
| --- | --- |
| health 连续失败 | 2 分钟内立即告警 |
| ready 为 release-blocked | 发布前阻断；运行期立即告警 |
| HTTP 5xx | 5 分钟 > 2% 或连续 5 次 |
| HTTP p95 | 普通 API 连续 10 分钟 > 1 秒 |
| 微信登录 401 | 关注突然上升，通常表示 code 过期/客户端重试错误 |
| 微信登录 429 | 关注平台配额或恶意重试 |
| 微信登录 503 | 立即检查凭据、微信接口和网络 |
| 管理登录失败 | 10 分钟内异常突增时检查攻击或凭据误配 |
| WebSocket 重连 | 同一版本异常上升时检查网络与实例重启 |

## 隐私规则

禁止在日志、span 和告警正文中写入 AppSecret、code、openid、unionid、customer token、管理密码/邀请码、完整数据库 URL、房间码、牌面或用户输入。故障排查使用 request id、状态码、固定结果枚举和耗时。

当前本地门禁不等于托管环境证据。正式发布仍需在独立 staging 上采集冷/热启动、Render 日志窗口和真实设备网络性能。
