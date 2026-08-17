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

assert.match(api, /getHomeBootstrap/);
assert.match(catalogApi, /export\s+async\s+function\s+getHomeBootstrap\s*\(/);
assert.match(catalogApi, /request\(["']\/bootstrap["']\)/);
assert.match(transport, /Taro\.request\s*\(/);
assert.doesNotMatch(api, /Taro\.request\s*\(/);
assert.match(routes, /Object\.freeze\s*\(/);
for (const name of ["GOMOKU", "FLIGHT", "LANDLORD", "ADMIN_DASHBOARD", "COUPLE_TASKS"]) {
  assert.match(routes, new RegExp(`\\b${name}\\s*:`));
}
assert.match(home, /await\s+getHomeBootstrap\s*\(\s*\)/);
assert.match(home, /Promise\.allSettled\s*\(\s*\[/);
assert.match(home, /getDishes\s*\(\s*\)/);
assert.match(home, /getFavoriteRanking\s*\(/);
assert.match(home, /getCoupleScore\s*\(/);
assert.match(appConfig, /pages\/index\/index/);
assert.match(appConfig, /pages\/games\/index/);
assert.match(appConfig, /pages\/couple\/index/);
assert.match(appConfig, /subPackages\s*:\s*\[/);

const compiledConfigPath = path.join(root, "dist", "app.json");
if (fs.existsSync(compiledConfigPath)) {
  const compiledConfig = JSON.parse(fs.readFileSync(compiledConfigPath, "utf8"));
  const roots = new Set((compiledConfig.subPackages || []).map((item) => item.root));
  assert.equal(compiledConfig.pages.includes("pages/games/flight/index"), false);
  assert.equal(compiledConfig.pages.includes("pages/admin-dashboard/index"), false);
  assert.equal(roots.has("pages/games/flight"), true);
  assert.equal(roots.has("pages/games/landlord"), true);
  assert.equal(roots.has("pages/admin-dashboard"), true);
}

console.log("LoveOS V3 bootstrap compatibility contracts passed.");
