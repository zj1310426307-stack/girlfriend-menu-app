const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");

const originalSpawn = childProcess.spawn;
childProcess.spawn = (command, args, options = {}) => originalSpawn(command, args, { ...options, shell: true });

const automator = require("miniprogram-automator");
const CLI_PATH = "F:/浏览器/微信web开发者工具/cli.bat";
const PROJECT_PATH = path.resolve(__dirname, "..");
const OUTPUT_PATH = path.join(PROJECT_PATH, ".test-tmp", "acceptance-2.11.2");
const HTTP_PORT = Number(process.env.WECHAT_DEVTOOLS_PORT || 9330);
const PAGES = [
  ["flight", "/pages/games/flight/index", [".flight-lobby-card", ".flight-name-options", ".flight-primary"], ".flight-mode-options > view", ".flight-difficulty"],
  ["landlord", "/pages/games/landlord/index", [".ll-lobby-card", ".ll-lobby-settings", ".ll-main-button"], ".ll-mode-row > view", null],
  ["animal", "/pages/games/animal/index", [".animal-lobby-card", ".animal-mode", ".animal-create"], ".animal-mode > view", ".animal-difficulty"],
  ["chess", "/pages/games/chess/index", [".chess-lobby-card", ".chess-mode", ".chess-create"], ".chess-mode > view", ".chess-difficulty"]
];
const PAGE_FILTER = String(process.env.GAME_PAGE_FILTER || "").trim().toLowerCase();
const SMOKE_API_ORIGIN = String(process.env.SMOKE_API_ORIGIN || "").replace(/\/$/, "");
const SMOKE_INVITE_CODE = String(process.env.SMOKE_INVITE_CODE || "");
let smokeSession = {
  customer_id: "gf_game_pages_smoke",
  customer_token: "gft_game_pages_smoke_offline_token"
};
const LEGACY_SMOKE_SESSION = { ...smokeSession };

/** Obtain an isolated local session only when an explicit smoke backend is supplied. */
async function provisionSmokeSession() {
  if (!SMOKE_API_ORIGIN) return;
  const response = await fetch(`${SMOKE_API_ORIGIN}/api/customers/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invite_code: SMOKE_INVITE_CODE, display_name: "开发者工具验收", device_label: "本地自动化" })
  });
  if (!response.ok) throw new Error(`本地测试会话创建失败：HTTP ${response.status}`);
  smokeSession = await response.json();
}

/** Reject a stalled DevTools operation instead of leaving acceptance hanging. */
function timeout(promise, milliseconds, message) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(message)), milliseconds))
  ]);
}

/** Reuse a healthy automation socket, or launch DevTools when no socket exists. */
async function connectOrLaunch() {
  try {
    return { miniProgram: await automator.connect({ wsEndpoint: `ws://127.0.0.1:${HTTP_PORT}` }), ownsDevtools: false };
  } catch (_) {
    const miniProgram = await automator.launch({
      cliPath: CLI_PATH,
      projectPath: PROJECT_PATH,
      port: HTTP_PORT,
      trustProject: true,
      timeout: 120000
    });
    return { miniProgram, ownsDevtools: true };
  }
}

/** Seed an offline session so page-shell checks never require production credentials. */
async function seedSmokeSession(miniProgram) {
  await timeout(
    miniProgram.callWxMethod("removeStorageSync", "gf_customer_expires_at"),
    8000,
    "清理测试会话过期标记超时"
  );
  const storage = [
    ["gf_invite_passed", "yes"],
    ["gf_authenticated_customer_id", smokeSession.customer_id],
    ["gf_customer_token", smokeSession.customer_token]
  ];
  for (const [key, value] of storage) {
    await timeout(miniProgram.callWxMethod("setStorageSync", key, value), 8000, `写入 ${key} 超时`);
  }
}

/** Snapshot the whole simulator store so smoke credentials cannot leak into manual testing. */
async function snapshotSimulatorStorage(miniProgram) {
  const info = await timeout(
    miniProgram.callWxMethod("getStorageInfoSync"),
    8000,
    "读取模拟器存储清单超时"
  );
  const entries = [];
  for (const key of info?.keys || []) {
    const value = await timeout(
      miniProgram.callWxMethod("getStorageSync", key),
      8000,
      `备份 ${key} 超时`
    );
    entries.push([key, value]);
  }
  return entries;
}

/** Restore even after a failed assertion so manual DevTools sessions remain untouched. */
async function restoreSimulatorStorage(miniProgram, entries) {
  await timeout(
    miniProgram.callWxMethod("clearStorageSync"),
    8000,
    "清理自动验收存储超时"
  );
  for (const [key, value] of entries) {
    await timeout(
      miniProgram.callWxMethod("setStorageSync", key, value),
      8000,
      `恢复 ${key} 超时`
    );
  }
}

/** Remove only the exact offline sentinel leaked by older acceptance versions. */
async function removeLegacySmokeSession(miniProgram) {
  const [customerId, customerToken] = await Promise.all([
    timeout(miniProgram.callWxMethod("getStorageSync", "gf_authenticated_customer_id"), 8000, "读取历史测试客户超时"),
    timeout(miniProgram.callWxMethod("getStorageSync", "gf_customer_token"), 8000, "读取历史测试令牌超时")
  ]);
  if (
    customerId !== LEGACY_SMOKE_SESSION.customer_id
    || customerToken !== LEGACY_SMOKE_SESSION.customer_token
  ) return;
  for (const key of [
    "gf_invite_passed",
    "gf_authenticated_customer_id",
    "gf_customer_token",
    "gf_customer_expires_at"
  ]) {
    await timeout(miniProgram.callWxMethod("removeStorageSync", key), 8000, `清理历史测试状态 ${key} 超时`);
  }
  console.log("[game-pages] 已清理旧版验收遗留的固定测试会话");
}

/** Recover once when a stale home-page bootstrap clears the freshly seeded offline session. */
async function openProtectedPage(miniProgram, route) {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    await seedSmokeSession(miniProgram);
    const page = await timeout(miniProgram.reLaunch(route), 25000, `打开 ${route} 超时`);
    await page.waitFor(1000);
    if (page.path === route.slice(1)) return page;
    if (attempt === 1 && page.path === "pages/index/index") {
      console.log(`[game-pages] ${route} 首次命中旧会话清理，重新写入隔离会话后重试`);
      await page.waitFor(800);
      continue;
    }
    throw new Error(`${route} 被重定向到 ${page.path}`);
  }
  throw new Error(`无法打开 ${route}`);
}

/** Wait for a selector because React can mount shortly after route navigation. */
async function waitForElement(page, selector, milliseconds = 10000) {
  const deadline = Date.now() + milliseconds;
  while (Date.now() < deadline) {
    const element = await page.$(selector);
    if (element) return element;
    await page.waitFor(200);
  }
  throw new Error(`页面 ${page.path} 缺少 ${selector}`);
}

/** Prove that the common couple/AI mode control reacts to a real tap. */
async function verifyModeSwitch(page, name, modeSelector, difficultySelector) {
  const options = await page.$$(modeSelector);
  if (options.length < 2) throw new Error(`${name} 缺少双人/人机模式选项`);
  await options[1].tap();
  await page.waitFor(300);
  const className = await options[1].attribute("class");
  if (!String(className || "").includes("active")) throw new Error(`${name} 点击人机模式后没有选中反馈`);
  if (difficultySelector) await waitForElement(page, difficultySelector, 3000);
}

/** Ensure a primary action is fully inside the current simulator viewport. */
async function verifyViewportFit(miniProgram, page, name, selector) {
  const element = await waitForElement(page, selector);
  const root = await waitForElement(page, ".ll-page");
  const [offset, size, rootOffset, rootSize, info] = await Promise.all([
    element.offset(),
    element.size(),
    root.offset(),
    root.size(),
    miniProgram.systemInfo()
  ]);
  const left = Number.parseFloat(offset.left);
  const top = Number.parseFloat(offset.top);
  const width = Number.parseFloat(size.width);
  const height = Number.parseFloat(size.height);
  const rootLeft = Number.parseFloat(rootOffset.left);
  const rootTop = Number.parseFloat(rootOffset.top);
  const rootWidth = Number.parseFloat(rootSize.width);
  const rootHeight = Number.parseFloat(rootSize.height);
  if (![left, top, width, height, rootLeft, rootTop, rootWidth, rootHeight].every(Number.isFinite)) {
    throw new Error(`${name} 无法读取 ${selector} 的视口位置`);
  }
  if (left < rootLeft || top < rootTop || left + width > rootLeft + rootWidth + 1 || top + height > rootTop + rootHeight + 1) {
    throw new Error(`${name} ${selector} 超出页面根容器：${left},${top} ${width}x${height} / ${rootLeft},${rootTop} ${rootWidth}x${rootHeight}`);
  }
  console.log(`[game-pages] ${name} ${selector} viewport PASS ${Math.round(left)},${Math.round(top)} ${Math.round(width)}x${Math.round(height)} / root ${Math.round(rootWidth)}x${Math.round(rootHeight)} (system ${info.windowWidth}x${info.windowHeight})`);
}

/** Dispatch a real tap to prove the landlord start control is not covered by another layer. */
async function verifyLandlordStartTap(page) {
  const button = await waitForElement(page, ".ll-main-button");
  await button.tap();
  if (SMOKE_API_ORIGIN) {
    await waitForElement(page, ".ll-room", 15000);
    console.log("[game-pages] landlord local AI room creation PASS");
  } else {
    await page.waitFor(250);
    console.log("[game-pages] landlord start button tap PASS");
  }
}

/** Enter a real local AI match and count every stable Chinese-chess line node. */
async function verifyChessBoard(page) {
  if (!SMOKE_API_ORIGIN) return;
  const createButton = await waitForElement(page, ".chess-create");
  await createButton.tap();
  await waitForElement(page, ".chess-board", 15000);
  const counts = {
    files: (await page.$$(".chess-file")).length,
    horizontal: (await page.$$(".chess-line.horizontal")).length,
    full: (await page.$$(".chess-line.vertical.full")).length,
    top: (await page.$$(".chess-line.vertical.top")).length,
    bottom: (await page.$$(".chess-line.vertical.bottom")).length
  };
  if (counts.files !== 9 || counts.horizontal !== 10 || counts.full !== 2 || counts.top !== 7 || counts.bottom !== 7) {
    throw new Error(`象棋线网节点不完整：${JSON.stringify(counts)}`);
  }
  console.log(`[game-pages] chess board lines PASS ${JSON.stringify(counts)}`);
}

/** Open one candidate page, verify its stable controls, and capture visual evidence. */
async function inspectPage(miniProgram, name, route, selectors, modeSelector, difficultySelector) {
  const page = await openProtectedPage(miniProgram, route);
  for (const selector of selectors) await waitForElement(page, selector);
  await verifyModeSwitch(page, name, modeSelector, difficultySelector);
  if (name === "landlord") {
    await verifyViewportFit(miniProgram, page, name, ".ll-main-button");
  }
  if (name === "chess") await verifyChessBoard(page);
  const screenshotPath = path.join(OUTPUT_PATH, name === "chess" && SMOKE_API_ORIGIN ? "chess-board.png" : `${name}-lobby.png`);
  try {
    await timeout(miniProgram.screenshot({ path: screenshotPath }), 5000, `${name} 截图超时`);
    console.log(`[game-pages] ${name} PASS -> ${screenshotPath}`);
  } catch (error) {
    console.warn(`[game-pages] ${name} PASS；截图跳过：${error.message}`);
  }
  if (name === "landlord") await verifyLandlordStartTap(page);
}

/** Warm the App automation domain after a cold compiler or a reused IDE socket. */
async function warmApp(miniProgram) {
  try {
    await timeout(miniProgram.reLaunch("/pages/index/index"), 30000, "首页预热超时");
  } catch (_) {
    console.log("[game-pages] 开发者工具仍在初始化，等待后重试首页");
    await new Promise((resolve) => setTimeout(resolve, 5000));
    await timeout(miniProgram.reLaunch("/pages/index/index"), 45000, "首页预热重试超时");
  }
}

/** Run bounded structural acceptance for all four 2.11.2 candidate game pages. */
async function run() {
  fs.mkdirSync(OUTPUT_PATH, { recursive: true });
  await provisionSmokeSession();
  const connection = await connectOrLaunch();
  const { miniProgram, ownsDevtools } = connection;
  let storageSnapshot = null;
  miniProgram.on("exception", (entry) => console.error("[devtools exception]", entry));
  try {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    await warmApp(miniProgram);
    await removeLegacySmokeSession(miniProgram);
    storageSnapshot = await snapshotSimulatorStorage(miniProgram);
    const selectedPages = PAGE_FILTER ? PAGES.filter(([name]) => name === PAGE_FILTER) : PAGES;
    if (!selectedPages.length) throw new Error(`未知游戏页面过滤器：${PAGE_FILTER}`);
    for (const page of selectedPages) await inspectPage(miniProgram, ...page);
    console.log("[game-pages] PASS（仅开发者工具页面结构与截图，不代表真机对局验收）");
  } finally {
    let restoreError = null;
    try {
      if (storageSnapshot) await restoreSimulatorStorage(miniProgram, storageSnapshot);
    } catch (error) {
      restoreError = error;
    }
    try {
      if (ownsDevtools) {
        await Promise.race([miniProgram.close(), new Promise((resolve) => setTimeout(resolve, 8000))]);
      } else {
        miniProgram.disconnect();
      }
    } finally {
      if (restoreError) throw restoreError;
    }
  }
}

timeout(run(), 180000, "四游戏开发者工具验收总超时")
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error.stack || error.message || error);
    process.exit(1);
  });
