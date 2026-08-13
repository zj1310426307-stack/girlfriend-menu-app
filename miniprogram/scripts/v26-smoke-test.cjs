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
const SMOKE_CUSTOMER_ID = "gf_v26_smoke";
const SMOKE_CUSTOMER_TOKEN = "gft_v26_smoke_offline_token";

/** Seed the minimum offline session required by protected page guards. */
async function seedSmokeSession(miniProgram) {
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_invite_passed", "yes"), 8000, "写入测试邀请码状态超时");
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_authenticated_customer_id", SMOKE_CUSTOMER_ID), 8000, "写入测试用户超时");
  await timeout(miniProgram.callWxMethod("setStorageSync", "gf_customer_token", SMOKE_CUSTOMER_TOKEN), 8000, "写入测试令牌超时");
}
const timeout = (promise, milliseconds, message) => Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error(message)), milliseconds))]);

/** Connect to an existing automation socket before asking the CLI to launch. */
async function connectOrLaunch() {
  try { return { miniProgram: await automator.connect({ wsEndpoint: `ws://127.0.0.1:${HTTP_PORT}` }), ownsDevtools: false }; }
  catch (_) {
    const miniProgram = await automator.launch({ cliPath: CLI_PATH, projectPath: PROJECT_PATH, args: ["--port", String(CLI_PORT)], port: HTTP_PORT, trustProject: true, timeout: 120000 });
    return { miniProgram, ownsDevtools: true };
  }
}

/** Poll one selector because Taro pages may mount after the route promise resolves. */
async function element(page, selector, milliseconds = 8000) {
  const deadline = Date.now() + milliseconds;
  while (Date.now() < deadline) {
    const found = await page.$(selector);
    if (found) return found;
    await page.waitFor(180);
  }
  throw new Error(`页面 ${page.path} 缺少 ${selector}`);
}

/** Open one route and allow its initial React render to settle. */
async function open(miniProgram, route) {
  await seedSmokeSession(miniProgram);
  const navigation = TAB_ROUTES.has(route) ? miniProgram.switchTab(route) : miniProgram.reLaunch(route);
  const page = await timeout(navigation, 20000, `打开 ${route} 超时`);
  await page.waitFor(900);
  return page;
}

/** Execute the bounded V2.6 structural smoke flow. */
async function run() {
  console.log("[v26] 连接微信开发者工具");
  const connection = await connectOrLaunch();
  const miniProgram = connection.miniProgram;
  const ownsDevtools = connection.ownsDevtools;
  try {
    await new Promise((resolve) => setTimeout(resolve, 4000));
    try { await timeout(miniProgram.reLaunch("/pages/index/index"), 30000, "首页冷启动超时"); }
    catch (_) { await new Promise((resolve) => setTimeout(resolve, 5000)); await timeout(miniProgram.reLaunch("/pages/index/index"), 45000, "首页冷启动重试超时"); }
    await seedSmokeSession(miniProgram);

    let page = await open(miniProgram, "/pages/games/index");
    await element(page, ".chess-feature-card");
    await element(page, ".game-data-card");
    page = await open(miniProgram, "/pages/games/chess/index");
    await element(page, ".chess-lobby-card");
    await element(page, ".chess-mode");
    await element(page, ".chess-create");
    page = await open(miniProgram, "/pages/games/ranking/index");
    await element(page, ".ranking-hero");
    page = await open(miniProgram, "/pages/games/ai/index");
    await element(page, ".ai-hero");
    await element(page, ".ai-chat-card");
    console.log("[v26] PASS");
  } finally {
    if (ownsDevtools) await Promise.race([miniProgram.close(), new Promise((resolve) => setTimeout(resolve, 8000))]);
    else miniProgram.disconnect();
  }
}

timeout(run(), 160000, "V2.6 冒烟测试总超时")
  .then(() => process.exit(0))
  .catch((error) => { console.error(error.stack || error.message || error); process.exit(1); });
