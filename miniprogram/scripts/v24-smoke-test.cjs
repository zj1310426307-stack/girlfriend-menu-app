const childProcess = require("child_process");
const path = require("path");

const originalSpawn = childProcess.spawn;
childProcess.spawn = (command, args, options = {}) =>
  originalSpawn(command, args, { ...options, shell: true });

const automator = require("miniprogram-automator");
const CLI_PATH = "F:/浏览器/微信web开发者工具/cli.bat";
const PROJECT_PATH = path.resolve(__dirname, "..");
const HTTP_PORT = Number(process.env.WECHAT_DEVTOOLS_PORT || 9330);
const CLI_PORT = Number(process.env.WECHAT_DEVTOOLS_CLI_PORT || 9421);
const TAB_ROUTES = new Set(["/pages/index/index", "/pages/menu/index", "/pages/my-orders/index", "/pages/games/index", "/pages/couple/index"]);
const SMOKE_CUSTOMER_ID = "gf_v24_smoke";
const SMOKE_CUSTOMER_TOKEN = "gft_v24_smoke_offline_token";

/** Seed the minimum offline session required by protected page guards. */
async function seedSmokeSession(miniProgram) {
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_invite_passed", "yes"), 8000, "写入测试邀请码状态超时");
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_authenticated_customer_id", SMOKE_CUSTOMER_ID), 8000, "写入测试用户超时");
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_customer_token", SMOKE_CUSTOMER_TOKEN), 8000, "写入测试令牌超时");
}

/** Connect to an existing automation socket before asking the CLI to launch. */
async function connectOrLaunch() {
  try {
    return { miniProgram: await automator.connect({ wsEndpoint: `ws://127.0.0.1:${HTTP_PORT}` }), ownsDevtools: false };
  } catch (_) {
    const miniProgram = await automator.launch({ cliPath: CLI_PATH, projectPath: PROJECT_PATH, args: ["--port", String(CLI_PORT)], port: HTTP_PORT, trustProject: true, timeout: 120000 });
    return { miniProgram, ownsDevtools: true };
  }
}

const timeout = (promise, milliseconds, message) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(message)), milliseconds))
]);

/** Wait for React to mount one stable page marker. */
async function element(page, selector, milliseconds = 7000) {
  const deadline = Date.now() + milliseconds;
  while (Date.now() < deadline) {
    const found = await page.$(selector);
    if (found) return found;
    await page.waitFor(180);
  }
  throw new Error(`页面 ${page.path} 缺少 ${selector}`);
}

/** Navigate with the API required by tab and non-tab routes. */
async function open(miniProgram, route) {
  await seedSmokeSession(miniProgram);
  const navigation = TAB_ROUTES.has(route) ? miniProgram.switchTab(route) : miniProgram.reLaunch(route);
  const page = await timeout(navigation, 18000, `打开 ${route} 超时`);
  await page.waitFor(900);
  return page;
}

/** Execute the bounded V2.4 structural smoke flow. */
async function run() {
  console.log("[v24] 连接微信开发者工具");
  const connection = await connectOrLaunch();
  const miniProgram = connection.miniProgram;
  const ownsDevtools = connection.ownsDevtools;
  miniProgram.on("exception", (entry) => console.error("[devtools exception]", entry));
  try {
    await new Promise((resolve) => setTimeout(resolve, 4000));
    try {
      await timeout(miniProgram.reLaunch("/pages/index/index"), 30000, "初始化小程序首页超时");
    } catch (_) {
      // The first Taro compile can outlive the automation handshake on a cold
      // DevTools process; retry once after the compiler has settled.
      console.log("[v24] 开发者工具仍在冷启动，等待后自动重试首页");
      await new Promise((resolve) => setTimeout(resolve, 5000));
      await timeout(miniProgram.reLaunch("/pages/index/index"), 45000, "冷启动重试首页仍然超时");
    }
    await seedSmokeSession(miniProgram);

    let page = await open(miniProgram, "/pages/games/index");
    await element(page, ".game-library-grid");
    await element(page, ".gomoku-feature-card");
    console.log("[v24] 游戏大厅：飞行棋与五子棋入口正常");

    page = await open(miniProgram, "/pages/games/flight/index");
    await element(page, ".flight-lobby-card");
    await element(page, ".flight-name-options");
    await element(page, ".flight-primary");
    console.log("[v24] 飞行棋大厅：创建、加入和姓名选择正常");

    page = await open(miniProgram, "/pages/couple/index");
    await element(page, ".love-score-card");
    await element(page, ".couple-tasks-entry");
    console.log("[v24] 情侣中心：默契值与今日任务入口正常");

    page = await open(miniProgram, "/pages/couple/tasks");
    await element(page, ".tasks-progress-card");
    await element(page, ".tasks-hero");
    console.log("[v24] 每日任务：进度和任务容器正常");

    console.log("[v24] PASS");
  } finally {
    if (ownsDevtools) {
      await Promise.race([
        miniProgram.close(),
        new Promise((resolve) => setTimeout(resolve, 8000))
      ]);
    } else {
      miniProgram.disconnect();
    }
  }
}

timeout(run(), 150000, "V2.4 冒烟测试总超时")
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error.stack || error.message || error);
    process.exit(1);
  });
