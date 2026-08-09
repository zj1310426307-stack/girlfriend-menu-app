const childProcess = require("child_process");
const path = require("path");

const originalSpawn = childProcess.spawn;
childProcess.spawn = (command, args, options = {}) => originalSpawn(command, args, { ...options, shell: true });
const automator = require("miniprogram-automator");
const CLI_PATH = "F:/浏览器/微信web开发者工具/cli.bat";
const PROJECT_PATH = path.resolve(__dirname, "..");
const HTTP_PORT = Number(process.env.WECHAT_DEVTOOLS_PORT || 9330);
const CLI_PORT = Number(process.env.WECHAT_DEVTOOLS_CLI_PORT || 9421);
const SMOKE_API_ORIGIN = (process.env.SMOKE_API_ORIGIN || "").replace(/\/$/, "");
let smokeSession = { customer_id: "gf_smoke_v28", customer_token: "gft_smoke_offline_token" };
const timeout = (promise, ms, message) => Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error(message)), ms))]);

async function createSmokeSession() {
  if (!SMOKE_API_ORIGIN) return;
  const response = await fetch(`${SMOKE_API_ORIGIN}/api/customers/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ invite_code: process.env.SMOKE_INVITE_CODE || "smoke-invite", display_name: "冒烟测试" })
  });
  if (!response.ok) throw new Error(`创建冒烟设备会话失败：HTTP ${response.status}`);
  smokeSession = await response.json();
}

async function element(page, selector, milliseconds = 8000) {
  const deadline = Date.now() + milliseconds;
  while (Date.now() < deadline) {
    const found = await page.$(selector);
    if (found) return found;
    await page.waitFor(180);
  }
  throw new Error(`页面 ${page.path} 缺少 ${selector}`);
}

async function open(miniProgram, route) {
  // Structural smoke runs without contacting production. A deliberately fake
  // session keeps protected pages mounted long enough to verify their shells;
  // backend authentication is covered by pytest and real-device acceptance.
  await miniProgram.callWxMethod("setStorageSync", "gf_invite_passed", "yes");
  await miniProgram.callWxMethod("setStorageSync", "gf_authenticated_customer_id", smokeSession.customer_id);
  await miniProgram.callWxMethod("setStorageSync", "gf_customer_token", smokeSession.customer_token);
  const page = await timeout(miniProgram.reLaunch(route), 25000, `打开 ${route} 超时`);
  await page.waitFor(900);
  return page;
}

async function run() {
  console.log("[v28] 连接微信开发者工具（离线结构冒烟）");
  let miniProgram;
  let ownsDevtools = false;
  try {
    miniProgram = await automator.launch({ cliPath: CLI_PATH, projectPath: PROJECT_PATH, args: ["--port", String(CLI_PORT)], port: HTTP_PORT, trustProject: true, timeout: 120000 });
    ownsDevtools = true;
  } catch (error) {
    if (!/port .* in use/i.test(error?.message || "")) throw error;
    miniProgram = await automator.connect({ wsEndpoint: `ws://127.0.0.1:${HTTP_PORT}` });
  }
  miniProgram.on("exception", (entry) => console.error("[devtools exception]", entry));
  try {
    await createSmokeSession();
    await new Promise((resolve) => setTimeout(resolve, 3500));
    try {
      await timeout(miniProgram.reLaunch("/pages/index/index"), 30000, "首页冷启动超时");
    } catch (_) {
      await new Promise((resolve) => setTimeout(resolve, 5000));
      await timeout(miniProgram.reLaunch("/pages/index/index"), 45000, "首页冷启动重试超时");
    }
    await timeout(miniProgram.callWxMethod("setStorageSync", "gf_invite_passed", "yes"), 8000, "写入邀请码状态超时");
    let page = await open(miniProgram, "/pages/couple/index");
    await element(page, ".couple-profile-card");
    await element(page, ".couple-message-entry");
    page = await open(miniProgram, "/pages/couple/timeline");
    await element(page, ".timeline-tabs");
    await element(page, ".timeline-add");
    page = await open(miniProgram, "/pages/notifications/index");
    await element(page, ".notifications-head");
    page = await open(miniProgram, "/pages/games/index");
    await element(page, ".game-center-heading");
    await element(page, ".gomoku-feature-card");
    console.log("[v28] PASS");
  } finally {
    if (ownsDevtools) await Promise.race([miniProgram.close(), new Promise((resolve) => setTimeout(resolve, 8000))]);
    else miniProgram.disconnect();
  }
}

timeout(run(), 170000, "V2.7 冒烟测试总超时")
  .then(() => process.exit(0))
  .catch((error) => { console.error(error.stack || error.message || error); process.exit(1); });
