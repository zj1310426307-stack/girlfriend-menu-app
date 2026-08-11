const childProcess = require("child_process");
const fs = require("fs");
const path = require("path");

const originalSpawn = childProcess.spawn;
childProcess.spawn = (command, args, options = {}) => originalSpawn(command, args, { ...options, shell: true });
const automator = require("miniprogram-automator");

const CLI_PATH = "F:/浏览器/微信web开发者工具/cli.bat";
const PROJECT_PATH = path.resolve(__dirname, "..");
const SCREENSHOT_PATH = path.resolve(PROJECT_PATH, "dist", "landlord-landscape.png");
const HTTP_PORT = Number(process.env.WECHAT_DEVTOOLS_PORT || 9330);
const CLI_PORT = Number(process.env.WECHAT_DEVTOOLS_CLI_PORT || 9421);
const timeout = (promise, milliseconds, message) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(message)), milliseconds)),
]);

async function requireElement(page, selector) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    const element = await page.$(selector);
    if (element) return element;
    await page.waitFor(180);
  }
  throw new Error(`横屏斗地主缺少 ${selector}`);
}

/** Validate route orientation and the major landscape lobby regions. */
async function run() {
  const pageConfig = JSON.parse(fs.readFileSync(path.resolve(PROJECT_PATH, "dist", "pages", "games", "landlord", "index.json"), "utf8"));
  if (pageConfig.pageOrientation !== "landscape" || pageConfig.navigationStyle !== "custom") {
    throw new Error("斗地主编译配置缺少横屏或自定义导航声明");
  }
  let miniProgram;
  let ownsDevtools = false;
  try {
    miniProgram = await automator.launch({
      cliPath: CLI_PATH,
      projectPath: PROJECT_PATH,
      args: ["--port", String(CLI_PORT)],
      port: HTTP_PORT,
      trustProject: true,
      timeout: 180000,
    });
    ownsDevtools = true;
  } catch (error) {
    if (!/port .* in use/i.test(error?.message || "")) throw error;
    miniProgram = await automator.connect({ wsEndpoint: `ws://127.0.0.1:${HTTP_PORT}` });
  }

  miniProgram.on("exception", (entry) => console.error("[landlord exception]", entry));
  try {
    await new Promise((resolve) => setTimeout(resolve, 8000));
    try {
      await timeout(miniProgram.reLaunch("/pages/index/index"), 60000, "首页冷启动超时");
    } catch (_) {
      await new Promise((resolve) => setTimeout(resolve, 8000));
      await timeout(miniProgram.reLaunch("/pages/index/index"), 90000, "首页冷启动重试超时");
    }
    await timeout(miniProgram.callWxMethod("setStorageSync", "gf_invite_passed", "yes"), 8000, "邀请码缓存写入超时");
    await timeout(miniProgram.callWxMethod("setStorageSync", "gf_authenticated_customer_id", "gf_landscape_smoke"), 8000, "测试用户写入超时");
    await timeout(miniProgram.callWxMethod("setStorageSync", "gf_customer_token", "landscape-smoke-token"), 8000, "测试令牌写入超时");
    const page = await timeout(miniProgram.reLaunch("/pages/games/landlord/index"), 30000, "横屏斗地主打开超时");
    await page.waitFor(1800);
    await requireElement(page, ".ll-lobby");
    await requireElement(page, ".ll-hero");
    await requireElement(page, ".ll-lobby-settings");
    await requireElement(page, ".ll-main-button");
    const info = await miniProgram.systemInfo();
    await miniProgram.screenshot({ path: SCREENSHOT_PATH });
    console.log("[landlord] config PASS landscape + custom navigation");
    if (info.windowWidth > info.windowHeight) console.log(`[landlord] runtime PASS ${info.windowWidth}x${info.windowHeight}`);
    else console.warn(`[landlord] simulator stayed portrait ${info.windowWidth}x${info.windowHeight}; use the DevTools rotate control for visual QA`);
    console.log(`[landlord] screenshot ${SCREENSHOT_PATH}`);
  } finally {
    if (ownsDevtools) await Promise.race([miniProgram.close(), new Promise((resolve) => setTimeout(resolve, 8000))]);
    else miniProgram.disconnect();
  }
}

timeout(run(), 300000, "横屏斗地主冒烟测试总超时")
  .then(() => process.exit(0))
  .catch((error) => { console.error(error.stack || error.message || error); process.exit(1); });
