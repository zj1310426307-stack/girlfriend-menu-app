const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

const appConfig = read("src/app.config.js");
const buildConfig = read("config/index.js");
const catalog = read("src/api/modules/catalog.js");
const customer = read("src/utils/customer.js");
const dishCard = read("src/components/DishCard.jsx");
const home = read("src/pages/index/index.jsx");
const homeCss = read("src/pages/index/index.css");
const snapshot = read("src/utils/homeSnapshot.js");

assert.match(appConfig, /lazyCodeLoading:\s*["']requiredComponents["']/);
assert.match(buildConfig, /cache:\s*\{\s*enable:\s*false\s*\}/);
assert.match(catalog, /request\(["']\/bootstrap["'],\s*\{\s*timeout:\s*12000,\s*maxRetries:\s*0\s*\}\)/);
assert.match(catalog, /isApiCapabilityCoolingDown\(API_BASE_URL, BOOTSTRAP_CAPABILITY\)/);
assert.match(catalog, /markApiCapabilityUnavailable\(API_BASE_URL, BOOTSTRAP_CAPABILITY\)/);
assert.match(catalog, /clearApiCapabilityCooldown\(API_BASE_URL, BOOTSTRAP_CAPABILITY\)/);
assert.match(catalog, /error\.code\s*=\s*["']BOOTSTRAP_SCHEMA_MISMATCH["']/);
for (const root of ["detail", "cart", "order-detail", "notifications", "profile"]) {
  assert.match(appConfig, new RegExp(`root:\\s*["']pages/${root}["']`));
}
assert.match(dishCard, /\blazyLoad\b/);

assert.match(snapshot, /HOME_SNAPSHOT_MAX_AGE\s*=\s*24\s*\*\s*60\s*\*\s*60\s*\*\s*1000/);
assert.match(snapshot, /snapshot\?\.customerId\s*!==\s*customerId/);
assert.match(snapshot, /age\s*>\s*HOME_SNAPSHOT_MAX_AGE/);
assert.match(snapshot, /payload\.recent_order\s*===\s*null\s*\|\|\s*Array\.isArray\(payload\.recent_order\?\.items\)/);
assert.match(snapshot, /if \(invalid\)\s*{[\s\S]*Taro\.removeStorageSync\(HOME_SNAPSHOT_KEY\)/);
assert.match(snapshot, /export function readHomeSnapshot/);
assert.match(snapshot, /export function writeHomeSnapshot/);
assert.match(snapshot, /export function clearHomeSnapshot/);
assert.match(customer, /clearHomeSnapshot\(\)/);

assert.match(catalog, /export function getCachedDishes/);
assert.match(catalog, /writeHomeSnapshot\(getAuthenticatedCustomerId\(\), payload\)/);
assert.match(catalog, /try\s*{[\s\S]*Taro\.setStorageSync\(DISH_CACHE_KEY/);

assert.match(home, /useState\(createInitialHomeState\)/);
assert.match(home, /readHomeSnapshot\(customerId\)/);
assert.match(home, /getCachedDishes\(\{ maxAge: DISH_CACHE_MAX_AGE \}\)/);
assert.match(home, /homeRequestInFlightRef\s*=\s*useRef\(false\)/);
assert.match(home, /if \(homeRequestInFlightRef\.current\) return/);
assert.match(home, /setDishes\(await dishPromise\)/);
assert.match(home, /Promise\.allSettled\(secondaryPromises\)/);
assert.match(home, /BOOTSTRAP_COMPATIBILITY_FALLBACK_STATUS_CODES\s*=\s*new Set\(\[404, 405, 501\]\)/);
assert.match(home, /if \(!compatibilityFallback\) throw bootstrapError/);
assert.match(home, /loading\s*&&\s*hasHomeContent/);
assert.match(home, /loading\s*&&\s*!hasHomeContent/);
assert.doesNotMatch(home, /if \(!inviteChecked\)[\s\S]*startup-page/);
assert.match(homeCss, /home-skeleton-shimmer/);

console.log("home warm-launch/cache/loading contracts: PASS");
