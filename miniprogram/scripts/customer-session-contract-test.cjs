const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const api = fs.readFileSync(path.join(root, "src", "api", "index.js"), "utf8");
const customer = fs.readFileSync(path.join(root, "src", "utils", "customer.js"), "utf8");

assert.match(api, /request\("\/customers\/recover"/);
assert.match(api, /legacy_customer_id:\s*legacyCustomerId/);
assert.match(api, /preserveSession:\s*true/);
assert.match(api, /request\("\/customers\/revoke"/);
assert.match(customer, /gf_customer_expires_at/);
assert.match(customer, /Date\.parse\(expiresAt\)/);
assert.match(customer, /removeStorageSync\(CUSTOMER_EXPIRES_KEY\)/);
assert.doesNotMatch(
  customer.match(/export function clearCustomerSession\(\)[\s\S]*?\n}/)?.[0] || "",
  /removeStorageSync\(LEGACY_CUSTOMER_KEY\)/
);

console.log("customer session recovery/storage contract: PASS");
