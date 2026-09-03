# LoveOS V3 游戏测试报告

## 新增守卫

- 六游戏完整 lifecycle；
- 状态 adapter/transport manifest；
- 插件 AI 与 provider 对齐；
- 五子棋稳定动作与局面缓存；
- 骰子概率 AI 合法性与 50 ms 微预算；
- AI 结果 envelope 的预算证据；
- 五子棋 engine codec 完整 round-trip；
- 非实时游戏拒绝进入实时 codec。

## 已完成定向验证

`backend/tests/game` 加 V3 plugin、compatibility、AI mode、runtime/recovery 测试：25 passed。

## 全量结果

| 门禁 | 结果 |
| --- | --- |
| Ruff | PASS |
| pytest | PASS：190 passed，11 个 SQLAlchemy/Python 3.12 datetime deprecation warning |
| compileall | PASS |
| Alembic upgrade/current/head | PASS：`20260817_13` |
| import-linter | PASS：5 kept，0 broken |
| `npm run build:weapp` | PASS：2.42 min |
| `npm run test:ci` | PASS |
| `npm run test:games` | PASS |
| `npm run test:landlord` | PASS |
| 包体 | 主包 484,291 bytes；总包 864,114 bytes |

首次全量 pytest 暴露 `flight` alias 兼容建房被严格 realtime codec 拒绝：1 failed、189 passed。修复为按插件状态所有权返回 metadata-only compatibility codec 后，失败用例与 runtime 定向 8 项通过，最终全量 190 项通过；没有删除或放宽断言。

`git diff --check`：PASS；仅有 Windows 工作区的 LF→CRLF 提示，不是空白错误。
