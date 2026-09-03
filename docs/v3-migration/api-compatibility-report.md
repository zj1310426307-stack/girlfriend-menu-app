# LoveOS V3 API 兼容报告

验证日期：2026-08-17
基线提交：`641c0d612d2c5b77e731e43271e0b6462fdb52b9`

## 结论

V2 的 88 个 `/api/*` HTTP method/path 组合和 3 个 WebSocket 路径全部保留。V3 只新增 `GET /api/bootstrap`，因此当前为 89 个 `/api/*` HTTP 操作；连同 `GET /` 共 90 个业务 HTTP 操作。没有删除、改名或替换旧接口。

## 数量复核

| 类型 | V2 基线 | V3 当前 | 结果 |
| --- | ---: | ---: | --- |
| `/api/*` HTTP | 88 | 89 | PASS，新增 1 个 |
| GET | 43 | 44 | PASS，新增 bootstrap |
| POST | 37 | 37 | PASS |
| PUT | 2 | 2 | PASS |
| PATCH | 2 | 2 | PASS |
| DELETE | 4 | 4 | PASS |
| WebSocket | 3 | 3 | PASS |

WebSocket 路径仍为：

- `/ws/admin/orders`
- `/ws/game/{room_code}`
- `/ws/games/dice/{room_code}`

## 新接口与回退

`GET /api/bootstrap` 聚合首页原有的菜品、喜欢排行和情侣积分数据。测试直接比较它与三个旧接口的响应，结果完全一致。小程序先请求 bootstrap；非认证类失败时自动回退旧三个请求，因此前后端滚动发布不会让首页白屏。旧接口继续独立可用。

## 游戏兼容层

- `flight` 映射到持久类型 `aeroplane`。
- `animal` 映射到 `jungle`。
- `chess` 映射到 `chinese_chess`。
- 未安装 V3 插件的历史目录数据仍按旧目录语义返回，不会被注册表错误判定为不存在。
- 重连通过兼容服务分发到原有权威状态源；补齐了持久类型 `jungle` 的恢复路径。

## 自动证据

- `tests/test_router_contract.py`：冻结当前完整 HTTP/WS 表面。
- `tests/test_v3_api_compatibility.py`：从审计清单读取 V2 基线并验证其为当前路由子集。
- `tests/test_v3_bootstrap.py`：认证、等价响应和旧别名。
- `tests/test_v3_game_compatibility_adapter.py`：已注册及未知历史游戏的恢复语义。
- `docs/v3-migration/openapi-v3.json`：FastAPI OpenAPI 3.1 确定性快照。

最终后端测试：`182 passed, 11 warnings`。OpenAPI 快照检查通过。

## 回滚

回滚小程序首页对 bootstrap 的调用即可恢复为原三请求流程；服务端新增路由是只读且无模式依赖。游戏兼容服务可恢复为原路由分支，不需要修改或回滚生产数据。
