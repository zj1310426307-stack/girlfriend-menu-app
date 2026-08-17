# LoveOS V3 游戏代码删除报告

## 结果

删除生产文件 0，删除 API 0，删除表 0，删除迁移 0。

## 扫描结论

- `backend/ai/chess_ai.py`、`animal_ai.py`、`landlord_ai.py` 是旧 import 的稳定 shim；
- 飞行棋当前 renderer 是唯一经过小程序构建验证的生产 renderer；
- 小程序离线骰子 AI 与服务端平台 AI 服务不同运行场景；
- legacy API/WS 路径受兼容契约保护；
- 中国象棋专用表仍被历史功能引用；
- 没有取得足够引用与生产流量证据证明上述代码可安全删除。

本轮减少重复的方式是把恢复分派和实时 engine codec 集中，而不是删除兼容边界。
