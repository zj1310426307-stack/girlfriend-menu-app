const childProcess = require("child_process");
const path = require("path");

// Node 24 requires Windows batch files to be launched through a command shell.
const originalSpawn = childProcess.spawn;
childProcess.spawn = (command, args, options = {}) =>
  originalSpawn(command, args, { ...options, shell: true });

const automator = require("miniprogram-automator");

const CLI_PATH = "F:/浏览器/微信web开发者工具/cli.bat";
const PROJECT_PATH = path.resolve(__dirname, "..");
const SCREENSHOT_DIR =
  process.env.DICE_SCREENSHOT_DIR === "off"
    ? null
    : process.env.DICE_SCREENSHOT_DIR || process.env.TEMP;
const DEVTOOLS_HTTP_PORT = Number(process.env.WECHAT_DEVTOOLS_PORT || 9330);
const DEVTOOLS_HOSTS = ["127.0.0.2", "127.0.0.1"];
const DICE_ONLY = process.env.DICE_ONLY === "1" || process.argv.includes("--dice-only");
const KEEP_OPEN = process.argv.includes("--keep-open");
const STOP_BEFORE_OPEN = process.argv.includes("--stop-before-open");
// Hosted smoke credentials are injected only for this process. Keeping the
// invite out of source prevents a rotated staging secret from becoming stale
// or leaking into the repository and compiled mini-program.
const CUSTOMER_INVITE_CODE = String(
  process.env.WECHAT_SMOKE_CUSTOMER_INVITE_CODE || ""
).trim();

/**
 * Throw a readable error when an automated interaction does not meet a condition.
 */
function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function withTimeout(promise, timeout, message) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(message)), timeout))
  ]);
}

/**
 * WeChat DevTools can briefly stop answering automation calls while its
 * simulator recompiles. Retry only idempotent bootstrap operations so a
 * transient protocol timeout does not look like an application failure.
 */
async function retryBootstrapOperation(operation, failureMessage, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (attempt === attempts) break;
      console.log(`[smoke] 开发者工具暂未响应，重试启动步骤 ${attempt}/${attempts - 1}`);
      await new Promise((resolve) => setTimeout(resolve, 1200 * attempt));
    }
  }
  const detail = String(lastError?.message || "unknown").replace(/https?:\/\/\S+/g, "[redacted-url]");
  throw new Error(`${failureMessage}：${detail}`);
}

/**
 * Wait for a tap-driven route change without depending on a fixed compile delay.
 */
async function waitForCurrentPage(miniProgram, expectedPath, sourcePage) {
  const normalizedExpected = expectedPath.replace(/^\/+/, "");
  const expiresAt = Date.now() + 6000;
  let currentPage = await miniProgram.currentPage();

  while (
    Date.now() < expiresAt &&
    currentPage?.path?.replace(/^\/+/, "") !== normalizedExpected
  ) {
    await sourcePage.waitFor(300);
    currentPage = await miniProgram.currentPage();
  }

  return currentPage;
}

/**
 * A route may become current slightly before its first render is committed.
 */
async function waitForElement(page, selector, timeout = 6000) {
  const expiresAt = Date.now() + timeout;
  let element = await page.$(selector);

  while (!element && Date.now() < expiresAt) {
    await page.waitFor(150);
    element = await page.$(selector);
  }

  return element;
}

/**
 * Wait until a temporary loading element has left the render tree.
 */
async function waitForElementToDisappear(page, selector, timeout = 8000) {
  const expiresAt = Date.now() + timeout;
  let element = await page.$(selector);

  while (element && Date.now() < expiresAt) {
    await page.waitFor(180);
    element = await page.$(selector);
  }

  return !element;
}

/** Reuse one responsive automation socket or launch a fresh project instance. */
async function connectOrLaunch() {
  for (const host of DEVTOOLS_HOSTS) {
    try {
      const miniProgram = await automator.connect({
        wsEndpoint: `ws://${host}:${DEVTOOLS_HTTP_PORT}`
      });
      await withTimeout(
        miniProgram.callWxMethod("getSystemInfoSync"),
        8000,
        "现有开发者工具自动化连接没有响应"
      );
      return { miniProgram, ownsDevtools: false };
    } catch (_) {
      // Recent Windows DevTools builds may bind the IDE HTTP service to
      // 127.0.0.1 and the automator socket to 0.0.0.0 on the same port.
      // Trying 127.0.0.2 first avoids routing the WebSocket to the IDE server.
    }
  }

  const miniProgram = await automator.launch({
    cliPath: CLI_PATH,
    projectPath: PROJECT_PATH,
    port: DEVTOOLS_HTTP_PORT,
    trustProject: true,
    timeout: 120000
  });
  return { miniProgram, ownsDevtools: true };
}

/**
 * Verify invite entry, live dishes and the native WebGL dice game.
 * The test uses the installed WeChat DevTools and the deployed backend API.
 */
async function run() {
  assert(
    CUSTOMER_INVITE_CODE && CUSTOMER_INVITE_CODE.length <= 200,
    "缺少安全注入的 WECHAT_SMOKE_CUSTOMER_INVITE_CODE"
  );
  console.log("[smoke] 正在连接微信开发者工具");
  const { miniProgram, ownsDevtools } = await connectOrLaunch();
  let networkPolicyError = null;

  miniProgram.on("console", (entry) => {
    const serialized = JSON.stringify(entry || {});
    if (serialized.includes("[network]")) {
      console.log("[devtools network]", serialized);
    }
    if (serialized.includes("MINIPROGRAM_DOMAIN_NOT_ALLOWED")) {
      networkPolicyError = "微信小程序 request 合法域名未允许 staging API";
    }
    if (entry?.type === "error" || entry?.level === "error") {
      console.error("[devtools console]", entry);
    }
  });
  miniProgram.on("exception", (entry) => {
    console.error("[devtools exception]", entry);
  });

  try {
    // A freshly opened IDE may accept the automation socket before the
    // mini-program runtime can answer wx method calls.
    if (ownsDevtools) await new Promise((resolve) => setTimeout(resolve, 8000));
    console.log("[smoke] 清理缓存并验证邀请码");
    await retryBootstrapOperation(
      () => miniProgram.callWxMethod("clearStorageSync"),
      "当前开发者工具实例没有响应清缓存请求，请确认已打开本项目"
    );
    let page = await retryBootstrapOperation(
      () => miniProgram.reLaunch("/pages/index/index"),
      "当前开发者工具实例没有打开本项目，无法重新加载首页"
    );
    await page.waitFor(1500);
    console.log("[smoke] 首页已重新加载");

    const inviteTitle = await page.$(".invite-title");
    const inviteInput = await page.$(".invite-input");
    const inviteButton = await page.$(".invite-button");

    assert(inviteTitle && inviteInput && inviteButton, "冷启动后未渲染邀请码表单");

    const inviteText = await inviteTitle.text();
    await inviteInput.input(CUSTOMER_INVITE_CODE);
    // Taro commits controlled-input state asynchronously. Give the input event
    // one render turn before tapping so submitInvite never reads the previous
    // empty value from a fast automation sequence.
    await page.waitFor(300);
    await inviteButton.tap();

    // Poll in short intervals instead of one long wait. This keeps the
    // DevTools automation connection alive while a free Render service wakes.
    if (DICE_ONLY) {
      await page.waitFor(1800);
    } else {
      const menuExpiresAt = Date.now() + 70000;
      while (Date.now() < menuExpiresAt) {
        const readyHero = await page.$(".v2-home-title");
        const readyCards = await page.$$(".shared-dish-card");
        const readyError = await page.$(".state-box.error");
        const readyInviteError = await page.$(".invite-error");
        if (readyHero || readyCards.length > 0 || readyError || readyInviteError) break;
        await page.waitFor(800);
      }
    }
    console.log("[smoke] 邀请码已提交");

    const heroTitle = await page.$(".v2-home-title");
    const dishCards = await page.$$(".shared-dish-card");
    const menuError = await page.$(".state-box.error");
    const inviteError = await page.$(".invite-error");

    assert(!networkPolicyError, networkPolicyError);
    assert(!inviteError, `邀请码登录失败：${inviteError ? await inviteError.text() : "未知错误"}`);
    assert(heroTitle, "邀请码通过后未渲染菜单首页");
    if (!DICE_ONLY) {
      assert(
        dishCards.length > 0,
        menuError
          ? `菜单接口失败：${await menuError.text()}`
          : "菜单接口完成后没有渲染菜品"
      );

      console.log("[smoke] 验证一起玩 Tab、情侣中心与小程序管理入口");
      page = await miniProgram.switchTab("/pages/games/index");
      const gomokuEntry = await waitForElement(page, ".gomoku-enter", 4000);
      assert(gomokuEntry, "一起玩页面没有渲染五子棋入口");
      await gomokuEntry.tap();
      page = await waitForCurrentPage(miniProgram, "pages/games/gomoku/index", page);
      const gomokuLobby = await waitForElement(page, ".gomoku-lobby-card", 5000);
      assert(gomokuLobby, "五子棋大厅没有完整渲染");
      page = await miniProgram.navigateBack();

      const flightEntry = await waitForElement(page, ".flight-feature-card", 4000);
      assert(flightEntry, "一起玩页面没有渲染情侣飞行棋入口");
      await flightEntry.tap();
      page = await waitForCurrentPage(miniProgram, "pages/games/flight/index", page);
      const flightLobby = await waitForElement(page, ".flight-lobby-card", 5000);
      assert(flightLobby, "情侣飞行棋大厅没有完整渲染");
      page = await miniProgram.navigateBack();

      const wheelEntry = await waitForElement(page, ".wheel-game-entry", 4000);
      assert(wheelEntry, "一起玩页面没有渲染今晚转盘入口");
      await wheelEntry.tap();
      page = await waitForCurrentPage(miniProgram, "pages/wheel/index", page);
      const wheelCanvas = await waitForElement(page, ".wheel-canvas", 7000);
      const wheelAdd = await waitForElement(page, ".wheel-add", 3000);
      const wheelOptionsBefore = await page.$$(".wheel-option");
      assert(wheelCanvas && wheelAdd, "转盘页面没有完整渲染");
      assert(wheelOptionsBefore.length >= 2, "转盘选项少于 2 个");
      await wheelAdd.tap();
      await page.waitFor(300);
      const wheelOptionsAfter = await page.$$(".wheel-option");
      assert(wheelOptionsAfter.length === wheelOptionsBefore.length + 1, "添加转盘分区失败");
      page = await miniProgram.navigateBack();

      page = await miniProgram.switchTab("/pages/couple/index");
      const scoreCard = await waitForElement(page, ".love-score-card", 4000);
      const adminEntry = await waitForElement(page, ".couple-admin-link", 4000);
      const tasksEntry = await waitForElement(page, ".couple-tasks-entry", 4000);
      assert(scoreCard, "情侣中心没有渲染默契值卡片");
      assert(tasksEntry, "情侣中心没有渲染今日任务入口");
      assert(adminEntry, "情侣中心没有渲染小厨房管理入口");
      await tasksEntry.tap();
      page = await waitForCurrentPage(miniProgram, "pages/couple/tasks", page);
      assert(await waitForElement(page, ".tasks-progress-card", 5000), "每日任务页面没有完整渲染");
      page = await miniProgram.navigateBack();
      const returnedAdminEntry = await waitForElement(page, ".couple-admin-link", 4000);
      await returnedAdminEntry.tap();
      page = await waitForCurrentPage(miniProgram, "pages/admin-login/index", page);
      assert(await page.$(".mini-admin-password"), "小厨房登录页没有渲染密码框");
      page = await miniProgram.navigateBack();
      console.log("[smoke] 五子棋、飞行棋、转盘、每日任务、情侣中心与管理登录页正常");
    }

    console.log("[smoke] 进入原生 3D 骰子桌");
    page = await miniProgram.switchTab("/pages/games/index");
    const diceEntry = await waitForElement(page, ".dice-game-entry", 4000);
    assert(diceEntry, "一起玩页面没有渲染摇骰子入口");
    await diceEntry.tap();
    page = await waitForCurrentPage(miniProgram, "pages/dice/index", page);
    console.log(`[smoke] 骰子路由已打开：${page?.path || "unknown"}`);

    assert(
      page?.path?.replace(/^\/+/, "") === "pages/dice/index",
      "点击入口后没有进入摇骰子页面"
    );
    const gameCanvas = await waitForElement(page, ".dice-webgl-canvas", 7000);
    const primaryAction = await waitForElement(page, ".dice-primary-action", 7000);
    assert(gameCanvas, "原生 WebGL 骰子画布没有渲染");
    assert(primaryAction, "摇骰按钮没有渲染");
    console.log("[smoke] WebGL 画布节点已渲染");

    // The loading overlay disappears only after the WeChat WebGL node and the
    // lightweight native renderer have both initialized successfully.
    await waitForElementToDisappear(page, ".dice-canvas-overlay", 9000);
    const canvasError = await page.$(".dice-canvas-overlay.error");
    const loadingOverlay = await page.$(".dice-canvas-overlay");
    assert(
      !canvasError,
      canvasError ? `3D 初始化失败：${await canvasError.text()}` : "3D 初始化失败"
    );
    assert(!loadingOverlay, "原生 3D 骰子桌没有完成初始化");
    console.log("[smoke] 3D 场景已初始化");

    await primaryAction.tap();
    console.log("[smoke] 已触发物理摇骰");
    await page.waitFor(500);
    const rollingAction = await page.$(".dice-primary-action");
    assert(
      rollingAction && (await rollingAction.text()).includes("碰撞中"),
      "点击后没有进入骰子碰撞状态"
    );

    await page.waitFor(2900);
    const openHint = await waitForElement(page, ".dice-open-hint", 3000);
    const canvasShell = await page.$(".dice-canvas-shell");
    assert(openHint && canvasShell, "骰子停稳后没有显示上滑开盅入口");
    const boundaryMetrics = await page.$(".dice-boundary-metrics");
    assert(boundaryMetrics, "没有渲染骰盅边界诊断数据");
    const [
      maxDiceRadius,
      cupSafeRadius,
      minDiceSeparation,
      maxDiceTilt,
      settleMs,
      physicsSteps
    ] = (await boundaryMetrics.text())
      .split("|")
      .map(Number);
    assert(
      Number.isFinite(maxDiceRadius) && maxDiceRadius > 0 && cupSafeRadius > 0,
      "没有取得骰盅边界诊断数据"
    );
    assert(
      maxDiceRadius <= cupSafeRadius + 0.001,
      `骰子超出骰盅安全边界：${maxDiceRadius} > ${cupSafeRadius}`
    );
    assert(
      Number.isFinite(minDiceSeparation) && minDiceSeparation >= 1.18,
      `骰子之间发生重叠：最小中心距离 ${minDiceSeparation}`
    );
    assert(
      Number.isFinite(maxDiceTilt) && maxDiceTilt <= 0.001,
      `骰子没有平稳落在桌面：最大倾斜误差 ${maxDiceTilt}`
    );
    assert(
      Number.isFinite(settleMs) && settleMs >= 1700 && settleMs <= 3450,
      `物理停稳时间不在预期范围：${settleMs}ms`
    );
    assert(
      Number.isFinite(physicsSteps) && physicsSteps >= 180,
      `固定时间步执行不足：${physicsSteps}`
    );
    console.log("[smoke] 骰子已停稳，准备开盅");
    if (STOP_BEFORE_OPEN) {
      console.log("[smoke] 已停留在骰盅预览状态");
      return;
    }

    await canvasShell.touchstart({
      touches: [{ identifier: 0, clientX: 180, clientY: 420, pageX: 180, pageY: 420 }]
    });
    await canvasShell.touchmove({
      touches: [{ identifier: 0, clientX: 180, clientY: 280, pageX: 180, pageY: 280 }]
    });
    await canvasShell.touchend({
      touches: [],
      changeTouches: [{ identifier: 0, clientX: 180, clientY: 280, pageX: 180, pageY: 280 }],
      changedTouches: [{ identifier: 0, clientX: 180, clientY: 280, pageX: 180, pageY: 280 }]
    });
    await page.waitFor(1000);

    let bidControls = await waitForElement(page, ".dice-bid-controls", 3500);
    if (!bidControls) {
      const tapToOpenHint = await page.$(".dice-open-hint");
      assert(tapToOpenHint, "上滑后开盅提示意外消失");
      await tapToOpenHint.tap();
      bidControls = await waitForElement(page, ".dice-bid-controls", 3000);
    }
    const myDice = await page.$(".dice-value-row");
    assert(bidControls, "开盅后没有进入玩家叫骰阶段");
    assert(myDice, "开盅后没有显示自己的 5 颗骰子结果");
    console.log("[smoke] 开盅并进入叫骰阶段");
    const diceValueText = await myDice.text();
    const diceValues = diceValueText.match(/[1-6]/g) || [];
    assert(diceValues.length === 5, `骰子数量不是 5：${diceValues.length}`);
    if (SCREENSHOT_DIR) {
      console.log("[smoke] 正在保存模拟器截图");
      await miniProgram.screenshot({
        path: path.join(SCREENSHOT_DIR, "dice-native-webgl.png")
      });
    }

    console.log(
      JSON.stringify(
        {
          inviteText,
          heroText: await heroTitle.text(),
          dishCount: dishCards.length,
          dicePath: page.path,
          diceMode: "native-webgl",
          diceCount: diceValues.length,
          diceValues: diceValues.map(Number),
          maxDiceRadius,
          cupSafeRadius,
          minDiceSeparation,
          maxDiceTilt,
          settleMs,
          physicsSteps
        },
        null,
        2
      )
    );
  } finally {
    if (KEEP_OPEN || !ownsDevtools) {
      miniProgram.disconnect();
    } else {
      await Promise.race([
        miniProgram.close(),
        new Promise((resolve) => setTimeout(resolve, 8000))
      ]);
    }
  }
}

// Keep Node alive while the DevTools SDK is establishing its WebSocket session.
const keepAlive = setInterval(() => {}, 1000);

run()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(() => {
    clearInterval(keepAlive);
  });
