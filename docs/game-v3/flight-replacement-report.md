# 飞行棋开源替换评审

## 状态

`DEFERRED — CURRENT TARO RENDERER RETAINED`

## 已完成

- 确认飞行棋规则由后端 `flight.py` 与 `flight_service.py` 权威执行；
- 确认小程序 `FlightBoard` 只渲染服务器状态，不自行判胜；
- 飞行棋已作为 `aeroplane` 插件声明完整 lifecycle、AI 和 `FLIGHT_STATE` adapter；
- `flight` 旧类型、旧 API、情侣事件、任务与积分保持；
- 评估 Phaser 官方运行模型与微信小程序运行时边界。

## 未进行生产替换的原因

Phaser 官方教程依赖 HTML 页面并创建/挂载浏览器 Canvas。当前仓库没有经过真机验证的 DOM、纹理、输入和生命周期 adapter，也没有兼容本项目规则与许可证明确的 Ludo 实现。直接安装会把运行时风险和包体成本交给用户。

## 回滚与后续 PoC

PoC 必须位于飞行棋分包，通过 feature flag 与现有 `FlightBoard` 并存；未通过准入条件时删除 PoC 分支即可，生产路径不变。

## 验收解释

本轮满足“没有成熟兼容方案时不强行集成”的原则，但不声明“Phaser 已替换飞行棋”。若总验收把 Phaser 替换视为硬门槛，则该单项仍为 BLOCKED，不能伪造 PASS。
