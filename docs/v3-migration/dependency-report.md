# LoveOS V3 依赖审计与开源方案决策

审计日期：2026-08-17

## 当前生产依赖

### 后端

| 能力 | 依赖 | 结论 |
| --- | --- | --- |
| Web/API | FastAPI 0.115.12、Uvicorn 0.34.2 | 保留 |
| 数据访问 | SQLAlchemy 2.0.40、Alembic 1.14.1 | 保留 |
| 校验与配置 | Pydantic 2.11.4、pydantic-settings 2.14.2 | 保留 |
| 可观测性 | OpenTelemetry 1.44.0 | 保留并扩展 |
| 缓存/协调 | redis 5.2.1 | 保留，继续可选降级 |
| 图片 | Pillow 11.3.0、boto3 1.40.3 | 复用实现缩略图/WebP与对象存储 |
| 数据库驱动 | psycopg2-binary 2.9.10 | 保留 |

### 小程序

| 能力 | 依赖 | 结论 |
| --- | --- | --- |
| 框架 | Taro 4.2、React 18.3 | 保留 |
| 构建 | Webpack 5、Babel 7 | 保留 |
| 开发者工具自动化 | miniprogram-automator 0.12.1 | 保留 |

## 新方案调研

### Taro 分包：采用

Taro 全局配置支持微信小程序 `subPackages` 语义，可把非 TabBar 页面从主包移出。该能力来自现有框架，不增加生产依赖。

- 采用方式：先建立稳定路由清单和契约测试，再迁移后台、游戏详情、情侣二级页。
- 约束：TabBar 页必须保留在主包；当前游戏大厅和游戏页共用 `pages/games` 根目录，不能在不移动文件的情况下直接把同级游戏页分包。
- 官方资料：<https://docs.taro.zone/en/docs/app-config>

### FastAPI OpenAPI + Hey API：分阶段采用

FastAPI 自动生成 OpenAPI 3.1；官方文档推荐使用开源生成器，并以 Hey API 作为 TypeScript 方案示例。

- 第一阶段：把 OpenAPI 导出和兼容性快照纳入测试。
- 第二阶段：前端领域模块转 TypeScript 后引入生成客户端；现有 `Taro.request` 传输适配器继续负责微信环境。
- 本轮不立即生成全部客户端：当前前端是 JavaScript，直接加入大量生成文件不能带来编译期收益，还会扩大改动面。
- 官方资料：<https://fastapi.tiangolo.com/advanced/generate-clients/>

### Phaser：PoC 后再决定，不进入当前生产包

Phaser 的标准运行环境以浏览器 Canvas/WebGL 和 HTML 元素为中心。微信小程序 Canvas、Taro 运行时、包体积和触摸事件适配都需要额外验证。

- 优点：成熟渲染、场景、动画和资源系统。
- 风险：并不能直接替换服务端飞行棋规则；小程序运行时适配和包体积可能抵消收益。
- 决策：保留现有规则引擎，把渲染器接口化；只有独立分包 PoC 在真机通过且许可证清晰后才可引入。
- 官方资料：<https://docs.phaser.io/api-documentation/class/core-config>

### Colyseus：当前不采用

Colyseus 当前服务端面向 Node.js/Bun 与 TypeScript。项目已经有 FastAPI WebSocket、持久化状态、Redis、房间租约、重连令牌、幂等动作和回放。

- 引入成本：增加第二个服务运行时、部署单元、协议网关和数据一致性问题。
- 重复能力：房间、状态同步、重连和实时消息均已有实现。
- 决策：不引入；继续强化现有协议和插件注册。若未来出现独立大规模游戏集群需求，再以 ADR 重新评估。
- 官方资料：<https://docs.colyseus.io/server>

### Pillow WebP/缩略图：采用现有依赖

Pillow 已在生产依赖中并支持 WebP 读写。图片优化优先复用它，不新增图片处理框架。

- 保留原图与旧 URL。
- 新增可选缩略图参数或派生资源时，需设置尺寸上限、缓存键和内容类型。
- CDN 由对象存储/部署层配置，代码不硬编码供应商域名。
- 官方资料：<https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#webp>

## 新依赖门槛

任何新增生产依赖必须同时满足：

1. 解决当前可测量问题，而非只调整目录外观。
2. 与微信小程序或 FastAPI 运行时兼容。
3. 许可证可接受，维护活跃，安全更新路径清楚。
4. 包体积、启动时间、部署复杂度有前后对比。
5. 现有测试和旧 API 兼容快照全部通过。

## 本阶段依赖变化

当前审计阶段没有新增、升级或删除任何生产依赖。
