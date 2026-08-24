import Taro from "@tarojs/taro";

export const CART_STORAGE_KEY = "gf_menu_cart";
export const REPEAT_DRAFT_STORAGE_KEY = "gf_repeat_order_draft";
export const GAME_RECONNECT_STORAGE_PREFIX = "gf_game_reconnect_v31_";
const LEGACY_GAME_RECONNECT_STORAGE_PREFIX = "gf_game_reconnect_";
const ROOM_SESSION_STORAGE_PREFIX = "gf_room_session_";

/** Normalize one owner or room fragment before it becomes part of a storage key. */
function storageKeyFragment(value) {
  return encodeURIComponent(String(value || "").trim());
}

/** Build a reconnect key that cannot be shared by two authenticated customers. */
export function gameReconnectStorageKey(customerId, roomCode) {
  const owner = storageKeyFragment(customerId);
  const room = storageKeyFragment(String(roomCode || "").trim().toUpperCase());
  if (!owner || !room) return "";
  // `:` is percent-escaped inside both encoded fragments, so the owner/room
  // boundary cannot become ambiguous even if a future identifier contains `_`.
  return `${GAME_RECONNECT_STORAGE_PREFIX}${owner}:${room}`;
}

/** Remove one key without allowing a storage failure to interrupt logout or rotation. */
export function removeStorageBestEffort(key) {
  if (!key) return false;
  try {
    Taro.removeStorageSync(key);
    return true;
  } catch (error) {
    console.info("客户本地状态清理失败，将在下次会话继续清理", error?.message);
    return false;
  }
}

/** Discard the unsafe pre-owner reconnect key without ever reading its credential. */
function discardLegacyReconnectToken(roomCode) {
  const room = String(roomCode || "").trim().toUpperCase();
  if (room) removeStorageBestEffort(`${LEGACY_GAME_RECONNECT_STORAGE_PREFIX}${room}`);
}

/** Read only a reconnect credential owned by the requested authenticated customer. */
export function readSessionGameReconnectToken(customerId, roomCode) {
  discardLegacyReconnectToken(roomCode);
  const key = gameReconnectStorageKey(customerId, roomCode);
  if (!key) return "";
  try {
    const token = Taro.getStorageSync(key);
    return typeof token === "string" ? token : "";
  } catch (error) {
    console.info("游戏恢复凭证读取失败，将回退到在线恢复", error?.message);
    return "";
  }
}

/** Persist a reconnect credential under its authenticated customer owner. */
export function writeSessionGameReconnectToken(customerId, roomCode, token) {
  const key = gameReconnectStorageKey(customerId, roomCode);
  if (!key || typeof token !== "string" || !token) return false;
  try {
    Taro.setStorageSync(key, token);
    return true;
  } catch (error) {
    console.info("游戏恢复凭证保存失败，当前对局仍可继续", error?.message);
    return false;
  }
}

/** Remove one customer-owned reconnect credential after the server rejects it. */
export function removeSessionGameReconnectToken(customerId, roomCode) {
  discardLegacyReconnectToken(roomCode);
  return removeStorageBestEffort(gameReconnectStorageKey(customerId, roomCode));
}

/** List current storage keys defensively because cleanup must remain best effort. */
function listStorageKeys() {
  try {
    const keys = Taro.getStorageInfoSync?.()?.keys;
    return Array.isArray(keys) ? keys : [];
  } catch (error) {
    console.info("客户本地状态索引读取失败，将清理已知固定项", error?.message);
    return [];
  }
}

/** Clear private cart and game credentials while preserving public catalogue caches. */
export function clearSessionOwnedStorage() {
  const keys = new Set([CART_STORAGE_KEY, REPEAT_DRAFT_STORAGE_KEY]);
  listStorageKeys().forEach((key) => {
    if (
      key.startsWith(LEGACY_GAME_RECONNECT_STORAGE_PREFIX)
      || key.startsWith(ROOM_SESSION_STORAGE_PREFIX)
    ) keys.add(key);
  });
  keys.forEach(removeStorageBestEffort);
}
