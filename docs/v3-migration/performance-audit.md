# LoveOS V3 性能基线审计

审计日期：2026-08-17

## 测量边界

本文件记录可重复的本地工程基线，不把本地构建时间等同于微信真机启动时间，也不把 SQLite TestClient 延迟等同于 Render/PostgreSQL 网络延迟。`<2s` 首屏目标只能在体验版真机、真实网络和已部署后端上验收。

## 小程序构建产物

| 指标 | 基线 |
| --- | ---: |
| `dist` 文件数 | 137 |
| `dist` 总体积 | 803,033 bytes |
| `taro.js` | 133,191 bytes |
| `app.js` | 98,297 bytes |
| `base.wxml` | 61,702 bytes |
| `common.js` | 50,969 bytes |
| `vendors.js` | 19,340 bytes |

最大业务脚本：

| 文件 | 体积 |
| --- | ---: |
| `pages/games/flight/index.js` | 20,248 bytes |
| `pages/dice/index.js` | 18,657 bytes |
| `pages/games/landlord/index.js` | 17,337 bytes |
| `pages/games/chess/index.js` | 16,945 bytes |
| `pages/games/gomoku/index.js` | 16,134 bytes |
| `pages/dice-online/index.js` | 15,616 bytes |
| `pages/games/animal/index.js` | 15,491 bytes |

当前 31 个页面全部在主包。总包体尚未触及微信上限，但游戏和后台代码进入首包会增加解析与安装成本，分包是低风险优化方向。

## 启动请求

`app.jsx` 没有全局预取。首页当前并行请求：

1. 菜品列表；
2. 收藏排行；
3. 情侣积分。

游戏列表、游戏历史、成就、通知、AI 汇总均在对应页面进入后加载，已经符合“不要在 App Launch 一次加载全部模块”的原则。

V3 的 `/api/bootstrap` 目标是把首页必要数据聚合为一次数据库会话和一次网络往返；旧三个接口继续保留。前端必须具备回退逻辑，避免新旧后端部署窗口导致白屏。

## 后端热点

| 文件 | 大小 | 风险 |
| --- | ---: | --- |
| `game_runtime/manager.py` | 35,839 bytes | 连接、运行时、协议分发职责集中 |
| `models.py` | 28,690 bytes | 多领域模型集中 |
| `schemas.py` | 19,838 bytes | 多领域 API schema 集中 |
| `api/routes/games.py` | 18,505 bytes | 游戏类型分支和 adapter 集中 |
| `crud.py` | 18,221 bytes | 旧式数据访问门面较大 |
| `flight_service.py` | 14,060 bytes | 飞行棋应用服务集中 |

大文件不是自动删除或拆分的理由。只有当新边界有测试、导入契约和可观察收益时才迁移。

## 已有性能/可靠性能力

- Redis 状态缓存可选降级；没有 Redis 时保持正确性。
- 游戏动作带 client action ID、请求哈希和版本。
- 多实例房间使用租约和心跳。
- API 中间件记录 privacy-safe `duration_ms`。
- OpenTelemetry 核心已存在并默认关闭，避免测试/诊断副作用。
- 图片支持本地、数据库和 S3 兼容存储。

## 待补测指标

| 指标 | 测量方法 | 通过标准 |
| --- | --- | --- |
| 首页真机可交互 | 体验版，冷启动/热启动各 10 次 | P95 < 2s，需标注网络和机型 |
| 普通 API | 本地隔离库 + staging PostgreSQL 分开统计 | staging P95 < 300ms |
| 规则 AI | 固定局面重复运行，不含网络 | P95 < 100ms |
| 主包体积 | 构建后按主包/分包统计 | V3 不高于基线，重模块移出主包 |
| `/api/bootstrap` | 与三个旧请求对比总耗时和查询 | 一次请求且响应内容等价 |

## 优化优先级

1. 建立测量脚本和报告格式。
2. 新增 bootstrap 聚合，同时保留回退。
3. 建立路由常量后迁移非 TabBar 页面到分包。
4. 复用 Pillow 生成缩略图/WebP，并保留原图。
5. 拆分 API 门面与游戏注册，不以文件大小作为唯一目标。
6. 体验版真机采集后再做进一步性能优化。
