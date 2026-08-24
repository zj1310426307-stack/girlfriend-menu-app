const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const api = fs.readFileSync(path.join(root, "src", "api", "index.js"), "utf8");
const customer = fs.readFileSync(path.join(root, "src", "utils", "customer.js"), "utf8");
const gameRecovery = fs.readFileSync(path.join(root, "src", "utils", "gameRecovery.js"), "utf8");
const sessionOwnedStorage = fs.readFileSync(path.join(root, "src", "utils", "sessionOwnedStorage.js"), "utf8");
const gameSocket = fs.readFileSync(path.join(root, "src", "api", "gameSocket.js"), "utf8");
const home = fs.readFileSync(path.join(root, "src", "pages", "index", "index.jsx"), "utf8");

assert.match(api, /Taro\.login\(/);
assert.match(api, /request\("\/customers\/wechat-session"/);
assert.match(api, /export async function restoreWeChatCustomerSession/);
assert.match(api, /export async function bindCurrentCustomerToWeChat/);
assert.match(api, /WECHAT_CAPABILITY_FALLBACK_STATUS_CODES\s*=\s*new Set\(\[404, 405, 501, 503\]\)/);
assert.match(api, /WECHAT_CAPABILITY_FALLBACK_STATUS_CODES\.has\(error\.statusCode\)/);
assert.match(api, /isApiCapabilityCoolingDown\(API_BASE_URL, WECHAT_SESSION_CAPABILITY\)/);
assert.match(api, /markApiCapabilityUnavailable\(API_BASE_URL, WECHAT_SESSION_CAPABILITY\)/);
assert.match(api, /clearApiCapabilityCooldown\(API_BASE_URL, WECHAT_SESSION_CAPABILITY\)/);
assert.match(api, /getGames\s*=\s*\(\)\s*=>\s*request\(["']\/games["'],\s*\{\s*maxRetries:\s*0\s*\}\)/);
assert.match(api, /request\(["']\/games\/active["'],\s*\{[^}]*maxRetries:\s*0/);
assert.match(api, /request\("\/customers\/recover"/);
assert.match(api, /legacy_customer_id:\s*legacyCustomerId/);
assert.match(api, /preserveSession:\s*true/);
assert.match(api, /request\("\/customers\/revoke"/);
assert.match(customer, /gf_customer_expires_at/);
assert.match(customer, /Date\.parse\(expiresAt\)/);
assert.match(customer, /removeStorageBestEffort\(CUSTOMER_EXPIRES_KEY\)/);
assert.match(customer, /gf_wechat_identity_bound/);
assert.match(customer, /export function markWeChatIdentityBound/);
assert.match(customer, /export function getAuthenticatedCustomerId/);
assert.match(customer, /clearHomeSnapshot\(\)/);
assert.match(customer, /clearPageSnapshots\(\)/);
assert.match(customer, /clearSessionOwnedStorage\(\)/);
assert.match(customer, /previousCustomerId\s*&&\s*previousCustomerId\s*!==\s*session\.customer_id/);
assert.doesNotMatch(
  customer.match(/export function clearCustomerSession\(\)[\s\S]*?\n}/)?.[0] || "",
  /removeStorageSync\(LEGACY_CUSTOMER_KEY\)/
);
assert.match(sessionOwnedStorage, /gameReconnectStorageKey\(customerId, roomCode\)/);
assert.match(sessionOwnedStorage, /LEGACY_GAME_RECONNECT_STORAGE_PREFIX/);
assert.match(sessionOwnedStorage, /ROOM_SESSION_STORAGE_PREFIX/);
assert.match(gameRecovery, /getGameReconnectToken\(customerId, normalized\)/);
assert.doesNotMatch(gameSocket, /setStorageSync\(`gf_room_session_/);
assert.match(home, /restoreWeChatCustomerSession/);
assert.match(home, /bindCurrentCustomerToWeChat/);
assert.match(home, /if \(!hasInvitePassed\(\)\) passInvite\(\)/);
assert.match(home, /requestError\?\.statusCode === 401/);
assert.match(home, /clearInvite\(\)/);
assert.match(home, /Taro\.reLaunch\(\{ url: ROUTES\.HOME \}\)/);

console.log("customer session recovery/storage contract: PASS");
