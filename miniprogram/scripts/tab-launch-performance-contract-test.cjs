const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

const customer = read("src/utils/customer.js");
const snapshot = read("src/utils/pageSnapshot.js");
const transport = read("src/api/transport.js");
const notice = read("src/components/PageSyncNotice.jsx");
const menu = read("src/pages/menu/index.jsx");
const menuCss = read("src/pages/menu/index.css");
const orders = read("src/pages/my-orders/index.jsx");
const games = read("src/pages/games/index.jsx");
const couple = read("src/pages/couple/index.jsx");

assert.match(snapshot, /snapshot\?\.customerId\s*!==\s*customerId/);
assert.match(snapshot, /age\s*>\s*maxAge/);
assert.match(snapshot, /export function readPageSnapshot/);
assert.match(snapshot, /export function writePageSnapshot/);
assert.match(snapshot, /export function clearPageSnapshots/);
assert.match(snapshot, /export function claimPageRefresh/);
assert.match(snapshot, /export function releasePageRefresh/);
assert.match(snapshot, /PAGE_REFRESH_MIN_INTERVAL/);
assert.match(snapshot, /snapshot\?\.customerId === customerId/);
assert.match(customer, /clearPageSnapshots\(\)/);
assert.match(notice, /当前显示上次内容，点这里重新同步/);
assert.match(transport, /GET_REQUEST_TIMEOUT\s*=\s*15000/);
assert.match(transport, /MAX_GET_RETRIES\s*=\s*1/);
assert.match(transport, /Number\.isInteger\(options\.maxRetries\)/);

for (const [source, scope, refName] of [
  [menu, "menu", "menuLoadingRef"],
  [orders, "orders", "ordersLoadingRef"],
  [games, "games", "gamesLoadingRef"],
  [couple, "couple", "coupleLoadingRef"]
]) {
  assert.match(source, new RegExp(`readPageSnapshot\\(["']${scope}["']`));
  assert.match(source, new RegExp(`writePageSnapshot\\(["']${scope}["']`));
  assert.match(source, new RegExp(`${refName}\\s*=\\s*useRef\\(false\\)`));
  assert.match(source, new RegExp(`if \\(${refName}\\.current\\) return`));
  assert.match(source, new RegExp(`claimPageRefresh\\(["']${scope}["']`));
  assert.match(source, new RegExp(`releasePageRefresh\\(["']${scope}["']`));
  assert.match(source, /force:\s*true/);
  assert.match(source, /<PageSyncNotice/);
}

assert.match(menu, /getCachedDishes\(\{ maxAge: DISH_CACHE_MAX_AGE \}\)/);
assert.match(menu, /favoriteMutationVersionRef/);
assert.match(menu, /favoriteUpdatingRef\.current\.size === 0/);
assert.match(menu, /<View className=["']v2-category-tabs-track["']>/);
assert.match(menuCss, /\.v2-category-tabs-track\s*>\s*view\s*\{/);
assert.doesNotMatch(menuCss, /\.v2-category-tabs\s*>\s*view\s*\{/);
assert.match(orders, /loading\s*&&\s*!hasLoaded/);
assert.doesNotMatch(orders, /if \(loading\) return/);
assert.match(games, /Promise\.allSettled/);
assert.match(couple, /results\.every\(\(result\) => result\.status === "fulfilled"\)/);
assert.match(couple, /results\.some\(\(result\) => result\.status === "rejected"\)/);

console.log("tab warm-launch/cache/request-ownership contracts: PASS");
