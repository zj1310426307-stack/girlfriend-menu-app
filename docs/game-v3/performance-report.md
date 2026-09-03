# LoveOS V3 游戏性能报告

## 本地结果

| 指标 | P95 | 目标 | 状态 |
| --- | ---: | ---: | --- |
| Bootstrap API | 77.700 ms | < 300 ms | PASS |
| 五子棋 strategy AI | 0.648 ms | < 100 ms | PASS |
| 实时房间内存创建 | 0.038 ms | < 300 ms | PASS |
| 快照恢复 | 0.094 ms | < 3000 ms | PASS |
| 回放序列化 | 0.106 ms | < 1000 ms | PASS |

环境为本地 TestClient + 隔离 SQLite。以上是代码路径回归门槛，不替代 Render、真实 PostgreSQL/Redis、网络或微信真机证据。

小程序构建产物：主包 484,291 bytes，总包 864,114 bytes，与 V3 基线一致。

## 优化点

- 游戏恢复从游戏名分支变为 O(1) adapter map；
- 实时引擎构造/恢复集中到 codec，避免复制 JSON 恢复逻辑；
- provider 实例复用，五子棋重复局面命中 LRU；
- 两层搜索限制为前 8 个候选，避免指数级扩张；
- 快照写入继续合并快速动作并移出 event loop。
