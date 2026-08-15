# Phase 3.0 Precheck — BLOCKER

> 执行时间：2026-08-13（Asia/Shanghai）
>
> 决策：**STOP — 不进入 Phase 3.0 架构改造**

## 1. Blocker

强制基线在小程序 `npm run test:ci` 阶段失败。根据 Phase 3.0 Stop
Conditions，本轮停止配置中心、架构边界、ADR、可观测性和开源依赖接入；不在同一轮中修复旧测试后继续架构升级。

失败发生在：

```text
npm run test:ci
  -> npm run test:landlord
  -> AssertionError: 斗地主开局入口必须使用可禁用的原生微信按钮
```

## 2. 根因证据

这不是当前产品源码缺少原生按钮。提交 `845fa51` 中的
`miniprogram/src/pages/games/landlord/index.jsx` 实际包含：

- 从 `@tarojs/components` 导入 `Button`；
- `<Button className="ll-main-button">`；
- `disabled={Boolean(busy)}`；
- `aria-label="开始斗地主"`。

失败来自测试的换行符敏感文本匹配：

```js
jsx.includes('<Button\n          className="ll-main-button"')
```

当前 Git for Windows 全局配置为 `core.autocrlf=true`，相关文件状态为
`i/lf w/crlf`。只读诊断结果：

```text
HAS_LF_ONLY_PATTERN=False
HAS_CRLF_PATTERN=True
HAS_DISABLED_SEMANTIC=True
```

因此相同提交在 LF 工作区可通过，而在标准 CRLF 检出中会误报。Node 24
只是本次运行环境事实，没有证据表明它导致了该失败。

## 3. 已完成的基线结果

| 指标 | 结果 |
| --- | --- |
| Git SHA | `845fa51a649a3a2e4bec1200099618128a5b0b3d` |
| 分支 | `main`，与 `origin/main` 对齐 |
| 初始用户改动 | 仅未跟踪 `docs/THREAD_HANDOFF_2026-08-13.md`，来源明确且未改动 |
| Python | `3.12.13` |
| Node | `v24.17.0`；项目文档目标为 Node 22 |
| npm | `11.13.0` |
| Ruff | 通过，约 `0.21s` |
| Alembic 空库升级 | 通过，隔离 SQLite，约 `2.28s` |
| 实际 Alembic head | `20260812_12` |
| Python compileall | 通过，约 `2.80s` |
| 后端测试 | `110 passed`，11 条 SQLite datetime adapter 弃用警告 |
| 后端测试时间 | pytest `15.85s`；命令墙钟约 `17.60s` |
| `npm ci` | 通过，1224 packages，约 `80.15s` |
| 小程序生产构建 | 通过，Taro `4.2.0` |
| 构建时间 | 命令墙钟约 `154.58s`；Webpack 报告 `1.09m` |
| `dist` | 137 个文件，`803,033` bytes（约 `0.766 MiB`） |
| HTTP 操作 | 实际 `88` |
| WebSocket 路径 | 实际 `3` |
| `npm run test:ci` | **失败**，在其首个 `test:landlord` 子任务停止 |
| `npm run test:games` | 未继续执行 |
| 独立 `npm run test:landlord` | 未继续执行；同一脚本已在 `test:ci` 中失败 |
| `git diff --check` | 通过 |

本轮还发现两项文档漂移：旧材料记录的 Alembic head `20260811_11` 已被
数据库图片存储迁移 `20260812_12` 取代；旧材料记录的 87 个 HTTP 操作当前实际
为 88 个。它们需要在基线恢复后纳入 Phase 3.0 文档校正，不能在 blocker 状态下
顺带改写历史文档。

## 4. 影响

- 无法证明当前提交在受支持的 Windows 开发工作区中满足现有 CI 契约。
- 不能把此前 `110 passed` 或历史小程序测试结论直接沿用为本轮完整基线。
- 按任务书，本轮不得开始配置系统迁移、架构依赖检查、性能埋点或 OSS 接入。
- HTTP、WebSocket、数据库 Schema、Customer Session、Game Runtime 和小程序用户路径均未修改。

## 5. 备选方案

### A. 推荐：让契约测试与换行符无关

在独立的“基线修复”变更中，把精确 `\n` 匹配改为语义或空白无关检查，例如
`/\<Button\s+className="ll-main-button"/`，同时保留对
`disabled={Boolean(busy)}` 的独立断言。修复后在 LF 与 CRLF 工作区各验证一次。

优点：范围最小，只修复测试可移植性，不改变产品行为。回滚只需恢复该测试文件。

### B. 仓库级强制 LF

新增或调整 `.gitattributes`。这会影响更多文件的工作区表现和后续 diff，范围明显
大于当前问题，不建议作为首选修复。

### C. 只在 Linux CI 运行

可以绕过本地 CRLF 误报，但会保留 Windows 开发者无法可靠执行官方基线的问题，
因此不建议。

## 6. 推荐决策与恢复条件

推荐先批准一个独立、最小的测试可移植性修复，然后从 Round 0 开始重新执行全部
命令。只有以下项目全部通过，才恢复 Phase 3.0：

```text
Ruff
pytest
compileall
Alembic upgrade head
npm ci
build:weapp
test:ci
test:games
test:landlord
git diff --check
```

恢复后应以代码重新采集的 `20260812_12`、88 HTTP / 3 WebSocket 为真实基线，
而不是沿用旧文档数字。

## 7. 本轮变更边界

- 新增本 blocker/precheck 文档。
- 没有修改测试、业务代码、配置、依赖、迁移或现有历史文档。
- 没有提交、推送、合并、变基或上传微信版本。
- 隔离迁移数据库已从忽略的测试临时目录清理。
