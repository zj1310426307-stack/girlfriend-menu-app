# Phase 3.0-B1 Windows Pytest Temp Root Diagnosis & Baseline Recovery Review

执行日期：2026-08-14（Asia/Shanghai）

最终状态：

**PASS — BASELINE RESTORED — READY TO RESUME PHASE 3.0**

本报告只覆盖 Windows pytest 临时根目录 blocker 的诊断、最小环境修复和完整
基线重跑。未进入 Phase 3.0 架构改造。

## 1. 初始 blocker

默认命令：

```text
python -m pytest -q
```

初始结果为 `108 passed, 2 errors in 15.51s`。两个错误都发生在 pytest
`tmp_path` fixture 的 setup 阶段：

- `test_customer_session_migration_backfills_and_round_trips`
- `test_upload_rejects_extension_disguise_and_reencodes_image`

共同异常为：

```text
PermissionError: [WinError 5] Access is denied:
C:\Users\13104\AppData\Local\Temp\pytest-of-13104
```

这不是 Customer Session、Upload 或其他业务断言失败。

## 2. TEMP / TMP / gettempdir

使用后端虚拟环境中的 Python 3.12.13 只读采集：

| 项目 | 结果 |
|---|---|
| `TEMP` | `C:\Users\13104\AppData\Local\Temp` |
| `TMP` | `C:\Users\13104\AppData\Local\Temp` |
| `tempfile.gettempdir()` | `C:\Users\13104\AppData\Local\Temp` |
| 临时根是否存在 | 是 |
| 测试进程 Windows 身份 | `ZJ\CodexSandboxOffline` |
| `USERNAME` / `getpass.getuser()` | `13104` / `13104` |

最后两项解释了目录名冲突：进程安全主体是隔离账户，但 pytest 根据环境中的
用户名选择了 `pytest-of-13104`。

## 3. pytest temp root 状态

初始目标是：

```text
C:\Users\13104\AppData\Local\Temp\pytest-of-13104
```

只读检查结果：

- 目标存在且是目录；
- 创建时间为 `2026-07-16 21:43:52`，最后写入时间为
  `2026-08-03 21:05:06`；
- 属性只有 `Directory`，没有只读属性；
- 不是 junction、symlink 或其他 reparse point；
- 没有正在运行的 Python/pytest 进程；
- 直接子项只有 `pytest-19`、`pytest-20`、`pytest-21`；
- 递归元数据检查共发现 300 个目录、0 个文件、0 个 reparse point；
- 未发现非 pytest 用户数据。

因此该精确路径被证明是可安全处理的陈旧 pytest 专用残留。没有扫描、删除或
修改系统 Temp 中的任何其他目录。

## 4. ACL / owner 诊断

初始目录 owner 为 `ZJ\13104`。DACL 是受保护的，显式条目只有：

- `OWNER RIGHTS`：FullControl；
- `NT AUTHORITY\SYSTEM`：FullControl；
- `BUILTIN\Administrators`：FullControl。

实际执行 pytest 的 `ZJ\CodexSandboxOffline` 不在 ACL 中，因此它不能枚举目录，
`Get-Acl`、`icacls` 和子项读取都返回 Access Denied。实际 owner
`ZJ\13104` 可以在不使用 Windows 管理员提权的情况下读取和删除该目录。

这说明权限问题位于旧 pytest 根本身，而不是系统 Temp 根。没有执行 `takeown`、
ACL reset、递归 ACL 修改或系统级权限修改。

精确清理后，默认 pytest 自动重建同名目录；重建后的 owner 是
`ZJ\CodexSandboxOffline`，与当前测试执行身份一致，默认命令随即恢复。

## 5. 普通临时目录读写结果

在 `tempfile.gettempdir()` 下创建了 UUID 唯一的探针目录，并逐步验证：

| 步骤 | 结果 |
|---|---|
| 创建唯一目录 | PASS |
| 写入小文本文件 | PASS |
| 读取并核对文本 | PASS |
| 删除文本文件 | PASS |
| 删除唯一目录 | PASS |

探针已清理。因此排除分类 A“Windows TEMP 本身不可写”。

## 6. 默认 pytest 结果

环境修复前再次复现：

```text
108 passed, 2 errors in 15.51s
```

确认无 Python/pytest 残留进程并只删除已验证的精确 pytest 根后，默认命令连续
两次通过：

| 运行 | 结果 | pytest 时间 | 命令墙钟时间 |
|---|---|---:|---:|
| 修复后确认 | `110 passed, 11 warnings` | 16.28s | 17.27s |
| 完整 Gate 重跑 | `110 passed, 11 warnings` | 15.90s | 16.84s |

11 条 warning 都来自 `test_customer_session_migration.py`，内容是 Python 3.12
下 SQLite 默认 datetime adapter 的弃用提醒；没有隐藏或吞掉 warning。

## 7. 显式 `--basetemp` 结果

诊断实验使用后端内专用且可安全删除的目录：

```text
python -m pytest -q --basetemp=.pytest-tmp-b1
```

结果为 `110 passed, 11 warnings in 14.83s`。这证明测试代码本身可以全部通过，
故障集中在默认 pytest temp root。实验目录随后被精确清理，没有进入 Git 状态。

该实验只用于定位，没有把 `--basetemp` 永久写入 `pytest.ini`、脚本或 CI。

## 8. 最终根因分类

主分类：**C — `pytest-of-13104` owner / ACL 与测试执行身份不匹配**。

完整因果链是：

1. Windows 系统 Temp 对测试进程可正常读写；
2. 旧 `pytest-of-13104` 由 `ZJ\13104` 所有，并以 owner-only ACL 保护；
3. 当前测试实际由 `ZJ\CodexSandboxOffline` 执行，但环境用户名仍为 `13104`；
4. pytest 因此选择已有的 `pytest-of-13104`，却无权扫描它；
5. 两个使用 `tmp_path` 的测试在 fixture setup 阶段报错；
6. 清理已证明安全的旧 pytest 根后，由当前执行身份重建，默认 pytest 连续通过。

D 和 E 已被排除：异常不是某一个子目录单独损坏，也没有占用进程。F 是触发身份
分离的环境背景，但直接 blocker 是 C。没有证据表明业务代码或 pytest fixture
实现存在缺陷。

## 9. 是否修改仓库

B1 **没有修改仓库代码或测试配置**。没有增加永久 `basetemp`，因为证据表明这是
本机旧 pytest 根与隔离执行身份冲突；把本机故障固化到项目配置不符合最小修复
原则。

仓库中进入 B1 前已经存在的 B0 修改
`miniprogram/scripts/landlord-landscape-config-test.cjs` 被完整保护，本轮未继续编辑。

## 10. 若修改，为什么

B1 唯一新增的仓库文件是本复核报告，用于满足交付和审计要求。没有修改业务源码、
测试源码、`pytest.ini`、`pyproject.toml`、`.gitignore` 或 `.gitattributes`。

环境侧只执行了一项最小修复：在确认 owner、ACL、内容、链接和进程状态后，删除
精确路径 `C:\Users\13104\AppData\Local\Temp\pytest-of-13104`，交由 pytest
按官方默认行为重建。没有修改 ACL。

## 11. 修改文件

本轮新增：

- `docs/optimization/PHASE_3_0_B1_WINDOWS_PYTEST_REVIEW.md`

本轮未修改其他文件。B0 文件和此前已有的未跟踪文档均未重置、覆盖或清理。

## 12. 完整 Gate 结果

在默认 pytest 恢复后，从第一项开始重新执行全部门禁：

| Gate | 结果 | 真实结果 / 墙钟时间 |
|---|---|---|
| `python -m ruff check . ../scripts` | PASS | All checks passed / 0.16s |
| `python -m pytest -q` | PASS | 110 passed, 11 warnings in 15.90s / 16.84s |
| `python -m compileall -q .` | PASS | 2.55s |
| 隔离空库 `alembic upgrade head` | PASS | 升级至 `20260812_12` / 1.86s |
| `npm run build:weapp` | PASS | Taro/Webpack 构建成功 / 4.51s |
| `npm run test:ci` | PASS | landlord、games、session 全部通过 / 2.58s |
| `npm run test:games` | PASS | longevity、socket 全部通过 / 0.98s |
| `npm run test:landlord` | PASS | 两组斗地主契约通过 / 0.58s |
| `git diff --check` | PASS | exit 0 |

测试数据库使用 `backend/.test-tmp` 下的 B1 专用 SQLite 文件，验证后已删除；未接触
现有数据库。GitHub Actions / Linux 本轮未在本机运行：`NOT VERIFIED LOCALLY`。

## 13. Alembic head

使用全新隔离 SQLite 数据库从空库执行到 head：

```text
ALEMBIC_DB_HEAD=20260812_12
20260812_12 (head)
```

候选值 `20260812_12` 已由代码和实际升级结果重新确认。

## 14. HTTP / WebSocket 数量

通过导入当前 FastAPI app 并按实际 route/method 展开重新统计：

| 项目 | 数量 |
|---|---:|
| HTTP operations | 88 |
| HTTP unique operations | 88 |
| WebSocket paths | 3 |
| WebSocket unique paths | 3 |

WebSocket 路径为：

- `/ws/admin/orders`
- `/ws/game/{room_code}`
- `/ws/games/dice/{room_code}`

候选值 88 / 3 已由当前代码重新确认，没有沿用旧文档数字。

## 15. build 与 dist 信息

| 项目 | 结果 |
|---|---|
| Git SHA | `845fa51a649a3a2e4bec1200099618128a5b0b3d` |
| Branch | `main` |
| Python | `3.12.13` |
| Node | `v24.17.0` |
| npm | `11.13.0` |
| Taro CLI | `4.2.0` |
| Webpack reported compile | 386.44ms |
| `build:weapp` 命令墙钟时间 | 4.51s |
| `dist` 文件数 | 137 |
| `dist` 总大小 | 803,033 bytes（约 0.765832 MiB） |

## 16. Node 环境漂移

当前 Node 是 `v24.17.0`，项目 README 的目标是 Node 22，记录为：

**ENVIRONMENT DRIFT — NOT A B1 BLOCKER**

本轮构建和全部 Node 契约均通过。B1 没有升级、降级或改写 Node 配置；该差异应在
独立的环境一致性任务中处理。

## 17. 回滚方法

仓库代码和 pytest 配置没有 B1 修改，因此没有代码回滚动作。若只撤销交付物，可
删除本轮新增且尚未提交的
`docs/optimization/PHASE_3_0_B1_WINDOWS_PYTEST_REVIEW.md`。

被删除的旧 pytest 根只包含空的 pytest 残留目录，不能也无需恢复；pytest 已按
默认机制自动重建它。不要为了“回滚”而恢复旧 owner-only 冲突、修改系统 Temp
ACL，或还原那 300 个空目录。

B0 的 EOL portability 修改不属于 B1 回滚范围，本轮没有触碰。

## 18. 是否可以恢复 Phase 3.0

可以。默认 pytest 已连续两次通过，完整后端、小程序、Alembic 和 Git 差异门禁
全部通过，真实基线已重新采集，且 B1 没有把本机权限异常固化为仓库配置。

**PASS — BASELINE RESTORED — READY TO RESUME PHASE 3.0**

本轮到此停止；未自动进入 Phase 3.0，未 commit、push、merge、rebase，也未上传
微信版本。
