const childProcess = require("child_process");
const path = require("path");

const originalSpawn = childProcess.spawn;
childProcess.spawn = (command, args, options = {}) => originalSpawn(command, args, { ...options, shell: true });

const automator = require("miniprogram-automator");
const CLI_PATH = "F:/浏览器/微信web开发者工具/cli.bat";
const PROJECT_PATH = path.resolve(__dirname, "..");
const HTTP_PORT = Number(process.env.WECHAT_DEVTOOLS_PORT || 9330);
const CLI_PORT = Number(process.env.WECHAT_DEVTOOLS_CLI_PORT || 9421);
const TAB_ROUTES = new Set(["/pages/index/index", "/pages/menu/index", "/pages/my-orders/index", "/pages/games/index", "/pages/couple/index"]);
const SMOKE_CUSTOMER_ID = "gf_v25_smoke";
const SMOKE_CUSTOMER_TOKEN = "gft_v25_smoke_offline_token";

/** Seed the minimum offline session required by protected page guards. */
async function seedSmokeSession(miniProgram) {
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_invite_passed", "yes"), 8000, "写入测试邀请码状态超时");
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_authenticated_customer_id", SMOKE_CUSTOMER_ID), 8000, "写入测试用户超时");
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_customer_token", SMOKE_CUSTOMER_TOKEN), 8000, "写入测试令牌超时");
}

/** Connect to an existing automation socket before asking the CLI to launch. */
async function connectOrLaunch() {
  try { return { miniProgram: await automator.connect({ wsEndpoint: `ws://127.0.0.1:${HTTP_PORT}` }), ownsDevtools: false }; }
  catch (_) {
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

/** Execute the bounded V2.5 structural smoke flow. */
async function run() {
  console.log("[v25] 连接微信开发者工具");
  const connection = await connectOrLaunch();
  const miniProgram = connection.miniProgram;
  const ownsDevtools = connection.ownsDevtools;
  miniProgram.on("exception", (entry) => console.error("[devtools exception]", entry));
  try {
    await new Promise((resolve) => setTimeout(resolve, 4000));
    try {
      await timeout(miniProgram.reLaunch("/pages/index/index"), 30000, "初始化小程序首页超时");
    } catch (error) {
      // DevTools may finish the first full compile just after the automation
      // handshake timeout. One bounded retry makes cold-start CI deterministic.
      console.log("[v25] 开发者工具仍在冷启动，等待后自动重试首页");
      await new Promise((resolve) => setTimeout(resolve, 5000));
      await timeout(miniProgram.reLaunch("/pages/index/index"), 45000, "冷启动重试首页仍然超时");
    }
    await seedSmokeSession(miniProgram);

    let page = await open(miniProgram, "/pages/games/index");
    await element(page, ".v25-game-grid");
    await element(page, ".landlord-entry");
    await element(page, ".animal-entry");
    console.log("[v25] 游戏大厅：斗地主与斗兽棋入口正常");

    page = await open(miniProgram, "/pages/games/landlord/index");
    await element(page, ".ll-lobby-card");
    await element(page, ".ll-choice-row");
    await element(page, ".ll-main-button");
    console.log("[v25] 斗地主：创建、加入和 AI 风格选择正常");

    page = await open(miniProgram, "/pages/games/animal/index");
    await element(page, ".animal-lobby-card");
    await element(page, ".animal-mode");
    await element(page, ".animal-create");
    console.log("[v25] 斗兽棋：情侣/AI 模式大厅正常");

    page = await open(miniProgram, "/pages/couple/achievements");
    await element(page, ".couple-achievement-list");
    console.log("[v25] 情侣中心：持久化成就页可打开");
    console.log("[v25] PASS");
  } finally {
    if (ownsDevtools) {
      await Promise.race([miniProgram.close(), new Promise((resolve) => setTimeout(resolve, 8000))]);
    } else {
      miniProgram.disconnect();
    }
  }
}

timeout(run(), 150000, "V2.5 冒烟测试总超时")
  .then(() => process.exit(0))
  .catch((error) => { console.error(error.stack || error.message || error); process.exit(1); });
