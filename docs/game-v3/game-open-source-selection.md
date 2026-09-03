# LoveOS V3 游戏开源选型

## 原则

成熟开源方案只有在运行时、规则、许可证、数据与回滚边界均可证明时才进入生产。不存在兼容成熟方案时，保留经过测试的当前实现，不以“用了新库”代替工程收益。

## 评估矩阵

| 候选 | 官方能力 | 当前项目适配 | 决策 |
| --- | --- | --- | --- |
| Phaser 3 | 浏览器 HTML、WebGL/Canvas 游戏框架 | 微信小程序不是浏览器 DOM；Taro Canvas 节点需要适配；会增加主包与输入/纹理桥接 | 暂缓生产集成，先真机 PoC |
| Colyseus | Node.js/Bun TypeScript 房间服务器，默认 WebSocket transport | 会与 FastAPI WS、PostgreSQL 房间、Redis、lease、重连、幂等和回放形成第二套服务 | 不集成 |
| Stockfish | C++ UCI 国际象棋引擎，GPLv3 | 不是中国象棋/UCCI；分发还需履行 GPLv3 源码义务 | 不集成 |
| 通用 Ludo 仓库 | 多为特定棋盘/规则/UI 实现 | 与本项目双人、28 格、精确到达、情侣事件和后端权威规则不等价，许可证质量不一 | 未选中 |
| Taro / FastAPI / SQLAlchemy / Alembic / pytest | 已成熟集成 | 与当前小程序、API、事务和测试主链一致 | 继续复用 |

## 一手资料

- Phaser 官方入门：<https://docs.phaser.io/phaser/getting-started/making-your-first-phaser-game>
- Colyseus 官方服务端：<https://docs.colyseus.io/server>
- Stockfish 官方仓库与 GPLv3：<https://github.com/official-stockfish/Stockfish>

## Phaser PoC 准入条件

只有同时满足以下条件才允许替换飞行棋生产 renderer：

1. 微信开发者工具与至少一台真机能创建 Phaser canvas，无 DOM shim 崩溃；
2. 触摸、前后台、页面卸载、纹理释放和低内存恢复通过；
3. 不改变服务器权威移动、情侣事件和 API；
4. 分包增量、首帧和帧率满足预算；
5. 具备一键切回当前 `FlightBoard` 的 feature flag；
6. 依赖许可证和素材来源形成交付记录。
