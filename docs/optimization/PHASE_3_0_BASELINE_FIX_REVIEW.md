# Phase 3.0-B0 Baseline Portability Fix Review

> 执行日期：2026-08-14（Asia/Shanghai）
>
> 最终状态：**BLOCKED — DO NOT RESUME PHASE 3.0**

## 1. 原始失败

Phase 3.0 Round 0 在 Windows CRLF 工作区执行 `npm run test:ci` 时，
`test:landlord` 误报：

```text
AssertionError: 斗地主开局入口必须使用可禁用的原生微信按钮
```

源码实际已经使用 `@tarojs/components` 的 `Button`，并保留
`className="ll-main-button"`、`disabled={Boolean(busy)}` 与
`aria-label="开始斗地主"`。

## 2. 根因

原测试把 JSX 排版和 LF 换行写进精确字符串：

```js
jsx.includes('<Button\n          className="ll-main-button"')
```

Git for Windows 当前以 `core.autocrlf=true` 检出 CRLF，所以正确源码包含
`\r\n`，无法匹配只接受 `\n` 的字符串。失败属于测试可移植性问题，不是产品行为
回归。

## 3. 修改文件

本轮只修改：

- `miniprogram/scripts/landlord-landscape-config-test.cjs`
- `docs/optimization/PHASE_3_0_BASELINE_FIX_REVIEW.md`

没有修改斗地主 JSX/CSS、游戏规则、API、WebSocket、数据库、Customer Session、
依赖或 `.gitattributes`。

## 4. 修改前后测试逻辑

修改前把组件类型、class 和 LF 排版绑定在一个字符串中，并把禁用态合并在同一
断言里。

修改后保留并强化为两个独立契约：

```js
const nativeMainButtonPattern = /<Button\s+className=["']ll-main-button["']/;
const busyDisabledPattern = /disabled=\{Boolean\(busy\)\}/;
```

- 第一条只验证入口确实是原生 `Button` 且 class 正确；
- 第二条独立验证忙碌禁用态；
- 原有 `aria-label`、分享入口、布局顺序、横屏和其余斗地主断言全部保留；
- 没有删除断言或降低测试强度。

## 5. 为什么没有修改业务代码

业务源码已满足契约。修改源码排版只会掩盖测试对工作区换行符的错误依赖，并会让
同一问题在下一次 CRLF/LF 转换时复发。因此修复仅位于测试层，不改变任何运行时
行为或编译产物语义。

## 6. LF 验证结果

测试在内存中构造以下 LF fixture：

```text
<Button\n  className="ll-main-button"\n  disabled={Boolean(busy)}>
```

`nativeMainButtonPattern` 与 `busyDisabledPattern` 均通过。该 fixture 是
`npm run test:landlord` 的前置断言；专项命令最终通过。

## 7. CRLF 验证结果

测试把同一 fixture 通过 `replace(/\n/g, "\r\n")` 转换成 CRLF 文本，两个语义
正则均通过。当前真实工作区源码也是 CRLF，随后源码契约断言通过。

专项结果：

```text
[landlord] PASS compiled landscape config
[landlord] PASS lobby, table, opponents, actions and hand hierarchy
```

## 8. 完整测试结果

完整基线按规定顺序启动，但在 pytest 处停止：

| 门槛 | 结果 |
| --- | --- |
| Git SHA | `845fa51a649a3a2e4bec1200099618128a5b0b3d` |
| Python | `3.12.13` |
| Ruff | PASS，约 `0.16s` |
| `python -m pytest -q` | **FAIL：108 passed，2 fixture setup errors，约 14.30s** |
| `python -m compileall -q .` | NOT RUN — stopped after pytest failure |
| `python -m alembic -c alembic.ini upgrade head` | NOT RUN — stopped after pytest failure |
| `npm run build:weapp` | NOT RUN in final baseline |
| `npm run test:ci` | NOT RUN in final baseline |
| `npm run test:games` | NOT RUN in final baseline |
| `npm run test:landlord` | PASS as targeted blocker verification; not rerun after pytest stop |
| `git diff --check` | PASS；仅有 Windows LF/CRLF 转换提示 |

pytest 的两个错误都发生在 `tmp_path` fixture setup：

```text
PermissionError: [WinError 5]
C:\Users\13104\AppData\Local\Temp\pytest-of-13104
```

受影响测试为：

- `test_customer_session_migration_backfills_and_round_trips`
- `test_upload_rejects_extension_disguise_and_reencodes_image`

这不是断言失败；其余 108 项通过。但任务规定任何一项失败必须停止，因此没有使用
`run_tests.py`、`--basetemp` 或修改 pytest 配置来绕过指定的
`python -m pytest -q` 门槛。

## 9. HTTP / WebSocket 数量

本轮在 pytest 失败后停止，没有重新扫描公共路由。最近一次同一 Git SHA 的只读
代码扫描结果仍是 88 个 HTTP 操作、3 条 WebSocket 路径，但它不能替代本轮完整
基线成功后的重新采集。

本轮没有修改任何路由或协议文件。

## 10. Alembic head

本轮在 pytest 失败后停止，没有执行 Alembic 门槛。最近一次同一 Git SHA 的空库
迁移结果为 `20260812_12`，但最终完整基线未走到该步骤。

本轮没有修改模型、迁移或数据库配置。

## 11. git diff --check

PASS。Git 仅提示目标测试文件在工作区的 LF/CRLF 转换，不属于 whitespace error，
命令退出码为 0。

## 12. 回滚方法

回滚本次 EOL 修复只需恢复
`miniprogram/scripts/landlord-landscape-config-test.cjs` 中新增的两个正则、
LF/CRLF fixture 和拆分后的两条断言。不需要数据库降级、依赖回滚或产品代码回滚。

删除本 Review 文档即可回滚本轮文档。不要覆盖原有未跟踪的
`docs/THREAD_HANDOFF_2026-08-13.md` 或 `PHASE_3_0_PRECHECK.md`。

## 13. 是否满足恢复 Phase 3.0 条件

**不满足。** 斗地主 LF/CRLF blocker 已修复且专项通过，但完整成功门槛中的
`python -m pytest -q` 未通过。必须先在独立任务中解决或明确批准处理 Windows
pytest 临时目录权限问题，再从头重跑全部门槛；在此之前不得恢复 Phase 3.0。

## 14. 最终自检

- 业务代码变化：0
- 新生产依赖：0
- API / WebSocket / 数据库 / Customer Session 变化：0
- commit / push / merge / 微信上传：均未执行
- 最终结论：**BLOCKED — DO NOT RESUME PHASE 3.0**
