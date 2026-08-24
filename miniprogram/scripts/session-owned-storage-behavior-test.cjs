const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const babel = require("@babel/core");
const transformModulesCommonJS = require("@babel/plugin-transform-modules-commonjs");

const root = path.resolve(__dirname, "..");

/** Execute source modules after a narrow ESM-to-CommonJS transform with explicit mocks. */
function createSourceLoader(taro, mocks = {}) {
  const cache = new Map();

  /** Resolve one relative source import without invoking the production bundler. */
  function resolveSource(request, parentFile) {
    const base = path.resolve(path.dirname(parentFile), request);
    const candidates = [base, `${base}.js`, `${base}.jsx`, path.join(base, "index.js")];
    const match = candidates.find((candidate) => fs.existsSync(candidate));
    if (!match) throw new Error(`Cannot resolve ${request} from ${parentFile}`);
    return match;
  }

  /** Load and cache one actual application module while replacing only declared boundaries. */
  function load(relativeOrAbsolutePath) {
    const file = path.isAbsolute(relativeOrAbsolutePath)
      ? relativeOrAbsolutePath
      : path.join(root, relativeOrAbsolutePath);
    if (cache.has(file)) return cache.get(file).exports;

    const source = fs.readFileSync(file, "utf8");
    const transformed = babel.transformSync(source, {
      babelrc: false,
      configFile: false,
      filename: file,
      plugins: [transformModulesCommonJS],
      sourceType: "module"
    });
    const module = { exports: {} };
    cache.set(file, module);

    const localRequire = (request) => {
      if (request === "@tarojs/taro") return { __esModule: true, default: taro };
      if (Object.prototype.hasOwnProperty.call(mocks, request)) return mocks[request];
      if (request.startsWith(".")) return load(resolveSource(request, file));
      return require(request);
    };
    const execute = new Function("require", "module", "exports", "__filename", "__dirname", transformed.code);
    execute(localRequire, module, module.exports, file, path.dirname(file));
    return module.exports;
  }

  return load;
}

/** Build the synchronous subset of Taro storage and sockets used by the tested modules. */
function createTaroMock(seed = {}, { removeFailures = [] } = {}) {
  const storage = new Map(Object.entries(seed));
  const failingRemovals = new Set(removeFailures);
  const sockets = [];
  return {
    storage,
    sockets,
    getStorageSync(key) {
      return storage.get(key);
    },
    setStorageSync(key, value) {
      storage.set(key, value);
    },
    removeStorageSync(key) {
      if (failingRemovals.has(key)) throw new Error(`remove failed: ${key}`);
      storage.delete(key);
    },
    getStorageInfoSync() {
      return { keys: [...storage.keys()] };
    },
    connectSocket() {
      const handlers = {};
      const socket = {
        sent: [],
        onOpen(callback) { handlers.open = callback; },
        onMessage(callback) { handlers.message = callback; },
        onError(callback) { handlers.error = callback; },
        onClose(callback) { handlers.close = callback; },
        send(payload) { this.sent.push(payload); },
        close() {},
        emitOpen() { handlers.open?.(); },
        emitMessage(payload) { handlers.message?.(payload); }
      };
      sockets.push(socket);
      return socket;
    }
  };
}

/** Verify logout clears all known private state while preserving public and legacy identity data. */
function testSessionClearIsOwnedAndIdempotent() {
  const taro = createTaroMock({
    gf_customer_id: "legacy-device-owner",
    gf_authenticated_customer_id: "customer_a",
    gf_customer_token: "token-a",
    gf_customer_expires_at: "2099-01-01T00:00:00Z",
    gf_wechat_identity_bound: "1",
    gf_menu_cart: [{ id: 1 }],
    gf_repeat_order_draft: { source_order_id: 7 },
    gf_home_snapshot_v31: { customerId: "customer_a" },
    gf_tab_snapshots_v31: { menu: { customerId: "customer_a" } },
    gf_game_reconnect_ROOM01: "legacy-reconnect-secret",
    gf_game_reconnect_v31_customer_a_ROOM02: "owned-reconnect-secret",
    gf_game_reconnect_v31_customer_b_ROOM03: "other-reconnect-secret",
    gf_room_session_ROOM04: { room_session_token: "unused-secret" },
    gf_dishes_cache_v28: { savedAt: 1, items: [{ id: 1 }] }
  });
  const load = createSourceLoader(taro);
  const customer = load("src/utils/customer.js");

  customer.clearCustomerSession();
  customer.clearCustomerSession();

  for (const key of [
    "gf_authenticated_customer_id",
    "gf_customer_token",
    "gf_customer_expires_at",
    "gf_wechat_identity_bound",
    "gf_menu_cart",
    "gf_repeat_order_draft",
    "gf_home_snapshot_v31",
    "gf_tab_snapshots_v31",
    "gf_game_reconnect_ROOM01",
    "gf_game_reconnect_v31_customer_a_ROOM02",
    "gf_game_reconnect_v31_customer_b_ROOM03",
    "gf_room_session_ROOM04"
  ]) assert.equal(taro.storage.has(key), false, `${key} must be cleared`);
  assert.equal(taro.storage.get("gf_customer_id"), "legacy-device-owner");
  assert.deepEqual(taro.storage.get("gf_dishes_cache_v28"), { savedAt: 1, items: [{ id: 1 }] });
}

/** Verify token refresh preserves drafts but a real owner switch clears the old owner's state. */
function testSessionSaveClearsOnlyOnOwnerChange() {
  const sameOwnerTaro = createTaroMock({
    gf_authenticated_customer_id: "customer_a",
    gf_customer_token: "old-token",
    gf_menu_cart: [{ id: 1 }],
    gf_home_snapshot_v31: { customerId: "customer_a" }
  });
  const sameOwnerCustomer = createSourceLoader(sameOwnerTaro)("src/utils/customer.js");
  sameOwnerCustomer.saveCustomerSession({ customer_id: "customer_a", customer_token: "new-token" });
  assert.deepEqual(sameOwnerTaro.storage.get("gf_menu_cart"), [{ id: 1 }]);
  assert.equal(sameOwnerTaro.storage.has("gf_home_snapshot_v31"), true);

  const switchedTaro = createTaroMock({
    gf_customer_id: "legacy-device-owner",
    gf_authenticated_customer_id: "customer_a",
    gf_customer_token: "token-a",
    gf_wechat_identity_bound: "1",
    gf_menu_cart: [{ id: 1 }],
    gf_repeat_order_draft: { source_order_id: 7 },
    gf_home_snapshot_v31: { customerId: "customer_a" },
    gf_tab_snapshots_v31: { orders: { customerId: "customer_a" } },
    gf_game_reconnect_ROOM01: "legacy-secret",
    gf_game_reconnect_v31_customer_a_ROOM02: "owned-secret",
    gf_room_session_ROOM03: { room_session_token: "unused-secret" },
    gf_dishes_cache_v28: { savedAt: 1, items: [] }
  });
  const switchedCustomer = createSourceLoader(switchedTaro)("src/utils/customer.js");
  switchedCustomer.saveCustomerSession({
    customer_id: "customer_b",
    customer_token: "token-b",
    expires_at: "2099-02-01T00:00:00Z"
  });

  assert.equal(switchedTaro.storage.get("gf_authenticated_customer_id"), "customer_b");
  assert.equal(switchedTaro.storage.get("gf_customer_token"), "token-b");
  for (const key of [
    "gf_wechat_identity_bound",
    "gf_menu_cart",
    "gf_repeat_order_draft",
    "gf_home_snapshot_v31",
    "gf_tab_snapshots_v31",
    "gf_game_reconnect_ROOM01",
    "gf_game_reconnect_v31_customer_a_ROOM02",
    "gf_room_session_ROOM03"
  ]) assert.equal(switchedTaro.storage.has(key), false, `${key} must not cross owners`);
  assert.equal(switchedTaro.storage.get("gf_customer_id"), "legacy-device-owner");
  assert.deepEqual(switchedTaro.storage.get("gf_dishes_cache_v28"), { savedAt: 1, items: [] });
}

/** Verify cleanup remains best effort when one individual storage removal throws. */
function testStorageRemovalFailureDoesNotBlockLogout() {
  const taro = createTaroMock({
    gf_authenticated_customer_id: "customer_a",
    gf_customer_token: "token-a",
    gf_menu_cart: [{ id: 1 }],
    gf_repeat_order_draft: { source_order_id: 7 }
  }, { removeFailures: ["gf_menu_cart"] });
  const customer = createSourceLoader(taro)("src/utils/customer.js");
  const originalInfo = console.info;
  console.info = () => {};
  try {
    assert.doesNotThrow(() => customer.clearCustomerSession());
  } finally {
    console.info = originalInfo;
  }
  assert.equal(taro.storage.has("gf_customer_token"), false);
  assert.equal(taro.storage.has("gf_repeat_order_draft"), false);
}

/** Verify reconnect credentials are isolated by owner and legacy keys are discarded unread. */
async function testReconnectTokenOwnership() {
  const taro = createTaroMock({ gf_game_reconnect_ROOM01: "unsafe-legacy-token" });
  const issued = [];
  const reconnected = [];
  const load = createSourceLoader(taro, {
    "../api": {
      issueReconnectToken: async (customerId, roomCode) => {
        issued.push([customerId, roomCode]);
        return { reconnect_token: `token-${customerId}-${roomCode}` };
      },
      reconnectGame: async (token) => {
        reconnected.push(token);
        return { state: { phase: "playing" } };
      },
      sendPresence: async () => {}
    }
  });
  const storage = load("src/utils/sessionOwnedStorage.js");
  const recovery = load("src/utils/gameRecovery.js");

  assert.equal(recovery.getGameReconnectToken("customer_a", "room01"), "");
  assert.equal(taro.storage.has("gf_game_reconnect_ROOM01"), false);

  const tokenA = await recovery.ensureGameRecovery("customer_a", "room01");
  assert.equal(tokenA, "token-customer_a-ROOM01");
  assert.equal(recovery.getGameReconnectToken("customer_a", "ROOM01"), tokenA);
  assert.equal(recovery.getGameReconnectToken("customer_b", "ROOM01"), "");
  assert.notEqual(
    storage.gameReconnectStorageKey("customer_a", "ROOM01"),
    storage.gameReconnectStorageKey("customer_b", "ROOM01")
  );
  assert.notEqual(
    storage.gameReconnectStorageKey("customer_a_b", "ROOM01"),
    storage.gameReconnectStorageKey("customer_a", "B_ROOM01")
  );

  await recovery.ensureGameRecovery("customer_a", "ROOM01");
  assert.deepEqual(issued, [["customer_a", "ROOM01"]]);
  assert.deepEqual(await recovery.recoverGameRoom("customer_a", "ROOM01", async () => null), { phase: "playing" });
  assert.deepEqual(reconnected, [tokenA]);
}

/** Verify session protocol messages are forwarded without persisting their unused secret. */
function testSocketDoesNotPersistRoomSessionSecret() {
  const taro = createTaroMock();
  const events = [];
  const load = createSourceLoader(taro, {
    "../config/env": { WEBSOCKET_ORIGIN: "wss://example.test" },
    "../utils/customer": { getCustomerToken: () => "customer-token" }
  });
  const { connectGameRoom } = load("src/api/gameSocket.js");
  const connection = connectGameRoom({
    roomCode: "ROOM01",
    gameType: "gomoku",
    playerName: "我",
    onEvent: (event) => events.push(event)
  });
  const socket = taro.sockets[0];
  socket.emitOpen();
  socket.emitMessage({
    data: JSON.stringify({
      type: "session",
      data: { room_session_token: "must-not-be-stored", expires_at: "2099-01-01T00:00:00Z" }
    })
  });
  connection.close();

  assert.equal(taro.storage.has("gf_room_session_ROOM01"), false);
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "session");
}

/** Run every behavior check sequentially so failures identify one ownership boundary. */
async function main() {
  testSessionClearIsOwnedAndIdempotent();
  testSessionSaveClearsOnlyOnOwnerChange();
  testStorageRemovalFailureDoesNotBlockLogout();
  await testReconnectTokenOwnership();
  testSocketDoesNotPersistRoomSessionSecret();
  console.log("session-owned storage behavior: PASS");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
