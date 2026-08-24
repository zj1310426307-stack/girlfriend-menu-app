const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

const api = read("src/api/index.js");
const menu = read("src/pages/menu/index.jsx");
const dishCard = read("src/components/DishCard.jsx");
const orderDetail = read("src/pages/order-detail/index.jsx");
const adminOrders = read("src/pages/admin-orders/index.jsx");
const status = read("src/utils/status.js");
const transport = read("src/api/transport.js");

assert.match(menu, /favoriteUpdatingRef\s*=\s*useRef\(new Set\(\)\)/);
assert.match(menu, /favoriteUpdatingRef\.current\.has\(dish\.id\)/);
assert.match(menu, /favoriteUpdatingRef\.current\.add\(dish\.id\)/);
assert.match(menu, /finally\s*{[\s\S]*favoriteUpdatingRef\.current\.delete\(dish\.id\)/);
assert.match(menu, /favoriteBusy={favoriteUpdatingIds\.includes\(dish\.id\)}/);

assert.match(dishCard, /favoriteBusy\s*=\s*false/);
assert.match(dishCard, /favoriteBusy\s*\?\s*"is-busy"/);
assert.match(dishCard, /if\s*\(!favoriteBusy\)\s*onToggleFavorite\(dish\)/);
assert.match(dishCard, /resolveImageUrl\(dish\.image_url,\s*\{ maxWidth: compact \? 640 : 480 \}\)/);
assert.match(transport, /images\\\.unsplash\\\.com/);

assert.match(orderDetail, /orderLoadingRef\s*=\s*useRef\(false\)/);
assert.match(orderDetail, /if\s*\(!id\s*\|\|\s*orderLoadingRef\.current\)\s*return/);
assert.match(orderDetail, /orderLoadingRef\.current\s*=\s*true/);
assert.match(orderDetail, /finally\s*{[\s\S]*orderLoadingRef\.current\s*=\s*false/);
assert.match(orderDetail, /ACTIVE_ORDER_STATUSES\.includes\(order\.status\)/);
assert.match(orderDetail, /loadOrder\(orderId,\s*true\)/);
assert.doesNotMatch(orderDetail, /order\.status\s*!==\s*"已完成"/);
assert.match(orderDetail, /orderHeadline\(order\.status\)/);
assert.match(orderDetail, /ROUTES\.ORDERS/);
assert.match(orderDetail, /ROUTES\.MENU/);
assert.doesNotMatch(orderDetail, /\/pages\/index\/index/);

assert.match(status, /待接单:\s*"点菜已经送出去啦"/);
assert.match(status, /已完成:\s*"可以开吃啦"/);
assert.match(status, /order\.status\s*===\s*"暂时做不了"\)\s*return\s*"本次未制作"/);

assert.match(adminOrders, /appendUniqueOrders/);
assert.match(adminOrders, /loadingMoreRef\s*=\s*useRef\(false\)/);
assert.match(adminOrders, /readVersionRef\s*=\s*useRef\(0\)/);
assert.match(adminOrders, /requestVersion\s*!==\s*readVersionRef\.current/);
assert.match(adminOrders, /filterDraft/);
assert.match(adminOrders, /appliedFilters/);
assert.match(adminOrders, /mode="date"/);
assert.match(adminOrders, /status\s*===\s*"已完成"[\s\S]*确认完成订单/);
assert.match(adminOrders, /status\s*===\s*"暂时做不了"[\s\S]*确认暂时做不了/);
assert.match(adminOrders, /requestError\.statusCode\s*===\s*409/);
assert.match(adminOrders, /offline:\s*"实时连接已断开"/);
assert.match(
  api,
  /rollbackAdminOrderStatus\s*=\s*\(orderId, token, expectedStatus\)[\s\S]*?data:\s*expectedStatus\s*\?\s*\{\s*expected_status:\s*expectedStatus\s*\}\s*:\s*undefined/
);
assert.match(
  api,
  /updateAdminOrderStatus\s*=\s*\(orderId, status, token, expectedStatus\)[\s\S]*?data:\s*\{[\s\S]*?status,[\s\S]*?expected_status:\s*expectedStatus/
);
assert.match(
  adminOrders,
  /updateAdminOrderStatus\(order\.id,\s*status,\s*token,\s*order\.status\)/
);
assert.match(
  adminOrders,
  /rollbackAdminOrderStatus\(order\.id,\s*token,\s*order\.status\)/
);

console.log("core product flow contracts: PASS");
