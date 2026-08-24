const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

const api = read("src/api/index.js");
const catalogApi = read("src/api/modules/catalog.js");
const transport = read("src/api/transport.js");
const routes = read("src/config/routes.js");
const home = read("src/pages/index/index.jsx");
const appConfig = read("src/app.config.js");
const buildConfig = read("config/index.js");
const packageConfig = JSON.parse(read("package.json"));
const stagingEnv = read(".env.staging");

assert.match(api, /getHomeBootstrap/);
assert.match(catalogApi, /export\s+async\s+function\s+getHomeBootstrap\s*\(/);
assert.match(catalogApi, /request\(["']\/bootstrap["'],\s*\{\s*timeout:\s*12000,\s*maxRetries:\s*0\s*\}\)/);
assert.match(transport, /Taro\.request\s*\(/);
assert.doesNotMatch(api, /Taro\.request\s*\(/);
assert.match(routes, /Object\.freeze\s*\(/);
for (const name of ["GOMOKU", "FLIGHT", "LANDLORD", "ADMIN_DASHBOARD", "COUPLE_TASKS", "ORDER_DETAIL"]) {
  assert.match(routes, new RegExp(`\\b${name}\\s*:`));
}
assert.match(home, /await\s+getHomeBootstrap\s*\(\s*\)/);
assert.match(home, /Promise\.allSettled\s*\(\s*secondaryPromises\s*\)/);
assert.match(home, /getDishes\s*\(\s*\)/);
assert.match(home, /getFavoriteRanking\s*\(/);
assert.match(home, /getCoupleScore\s*\(/);
assert.match(home, /getTodayTasks\s*\(/);
assert.match(home, /getMyOrders\s*\(/);
assert.match(home, /bootstrap\.today_tasks/);
assert.match(home, /bootstrap\.recent_order/);
assert.match(home, /ROUTES\.COUPLE_TASKS/);
assert.match(home, /ROUTES\.ORDER_DETAIL/);
assert.match(appConfig, /pages\/index\/index/);
assert.match(appConfig, /pages\/games\/index/);
assert.match(appConfig, /pages\/couple\/index/);
assert.match(appConfig, /subPackages\s*:\s*\[/);
assert.match(buildConfig, /environmentName\s*===\s*["']staging["']/);
assert.match(buildConfig, /must not use the production API/);
assert.equal(
  packageConfig.scripts["build:weapp:staging"],
  "taro build --type weapp --env production --mode staging"
);
assert.match(stagingEnv, /^TARO_APP_ENV_NAME=staging$/m);
assert.doesNotMatch(stagingEnv, /girlfriend-menu-api\.onrender\.com/);

const compiledConfigPath = path.join(root, "dist", "app.json");
if (fs.existsSync(compiledConfigPath)) {
  const compiledConfig = JSON.parse(fs.readFileSync(compiledConfigPath, "utf8"));
  const roots = new Set((compiledConfig.subPackages || []).map((item) => item.root));
  assert.equal(compiledConfig.pages.includes("pages/games/flight/index"), false);
  assert.equal(compiledConfig.pages.includes("pages/admin-dashboard/index"), false);
  assert.equal(roots.has("pages/games/flight"), true);
  assert.equal(roots.has("pages/games/landlord"), true);
  assert.equal(roots.has("pages/admin-dashboard"), true);
  assert.equal(roots.has("pages/detail"), true);
  assert.equal(roots.has("pages/cart"), true);
  assert.equal(roots.has("pages/order-detail"), true);
  assert.equal(roots.has("pages/notifications"), true);
  assert.equal(roots.has("pages/profile"), true);
}

console.log("LoveOS V3 bootstrap compatibility contracts passed.");
