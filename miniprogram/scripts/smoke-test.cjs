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
const DEVTOOLS_HTTP_PORT = Number(process.env.WECHAT_DEVTOOLS_PORT || 9320);
const DICE_ONLY = process.env.DICE_ONLY === "1";

/**
 * Throw a readable error when an automated interaction does not meet a condition.
 */
function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
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
 * Verify invite entry, live dishes and the complete 3D game's web-view handoff.
 * The test uses the installed WeChat DevTools and the deployed backend API.
 */
async function run() {
  console.log("[smoke] 正在连接微信开发者工具");
  const miniProgram = await automator.launch({
    cliPath: CLI_PATH,
    projectPath: PROJECT_PATH,
    args: ["--port", String(DEVTOOLS_HTTP_PORT)],
    trustProject: true,
    timeout: 120000
  });

  try {
    console.log("[smoke] 清理缓存并验证邀请码");
    await miniProgram.callWxMethod("clearStorageSync");
    let page = await miniProgram.reLaunch("/pages/index/index");
    await page.waitFor(1500);

    const inviteTitle = await page.$(".invite-title");
    const inviteInput = await page.$(".invite-input");
    const inviteButton = await page.$(".invite-button");

    assert(inviteTitle && inviteInput && inviteButton, "冷启动后未渲染邀请码表单");

    const inviteText = await inviteTitle.text();
    await inviteInput.input("love2026");
    await inviteButton.tap();

    // Render may wake the free backend during the full menu test. Dice-only
    // checks only need the unlocked home screen and should stay fast.
    await page.waitFor(DICE_ONLY ? 1800 : 35000);

    const heroTitle = await page.$(".hero-title");
    const dishCards = await page.$$(".dish-card");
    const menuError = await page.$(".state-box.error");

    assert(heroTitle, "邀请码通过后未渲染菜单首页");
    if (!DICE_ONLY) {
      assert(
        dishCards.length > 0,
        menuError
          ? `菜单接口失败：${await menuError.text()}`
          : "菜单接口完成后没有渲染菜品"
      );
    }

    console.log("[smoke] 进入完整 3D 骰子 web-view");
    const diceEntry = await page.$(".dice-entry");
    assert(diceEntry, "首页没有渲染摇骰子入口");
    await diceEntry.tap();
    page = await waitForCurrentPage(miniProgram, "pages/dice/index", page);

    assert(
      page?.path?.replace(/^\/+/, "") === "pages/dice/index",
      "点击入口后没有进入摇骰子页面"
    );
    const gameWebView =
      (await waitForElement(page, ".dice-game-webview", 3000))
      || (await waitForElement(page, "web-view", 7000));
    assert(gameWebView, "完整 3D 游戏 web-view 没有渲染");
    const gameUrl = await gameWebView.attribute("src");
    assert(
      gameUrl === "https://girlfriend-menu-web-zj13104.onrender.com/games/dice?embed=weapp",
      `3D 游戏地址不正确：${gameUrl || "空"}`
    );
    if (SCREENSHOT_DIR) {
      await miniProgram.screenshot({
        path: path.join(SCREENSHOT_DIR, "dice-webview.png")
      });
    }

    console.log(
      JSON.stringify(
        {
          inviteText,
          heroText: await heroTitle.text(),
          dishCount: dishCards.length,
          dicePath: page.path,
          diceMode: "web-view",
          gameUrl
        },
        null,
        2
      )
    );
  } finally {
    await Promise.race([
      miniProgram.close(),
      new Promise((resolve) => setTimeout(resolve, 8000))
    ]);
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
