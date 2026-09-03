import Taro from "@tarojs/taro";
import { API_BASE_URL } from "../config/env";
import {
  clearApiCapabilityCooldown,
  isApiCapabilityCoolingDown,
  markApiCapabilityUnavailable
} from "../utils/apiCapability";
import { createGameActionId } from "../utils/gameAction";
import {
  clearCustomerSession,
  getLegacyCustomerId,
  hasCustomerSession,
  hasWeChatIdentityBinding,
  markWeChatIdentityBound,
  saveCustomerSession
} from "../utils/customer";
import { request } from "./transport";

export { API_BASE_URL };
export { resolveImageUrl } from "./transport";
export {
  addFavorite,
  DISH_CACHE_MAX_AGE,
  getCachedDishes,
  getDish,
  getDishes,
  getFavoriteRanking,
  getFavorites,
  getHomeBootstrap,
  removeFavorite
} from "./modules/catalog";

const customerHeader = () => ({});
const WECHAT_CAPABILITY_FALLBACK_STATUS_CODES = new Set([404, 405, 501, 503]);
const WECHAT_SESSION_CAPABILITY = "wechat-session";

/** Obtain one short-lived WeChat login code without assuming Promise support. */
function getWeChatLoginCode() {
  return new Promise((resolve, reject) => {
    Taro.login({
      timeout: 8000,
      success: (result) => result?.code ? resolve(result.code) : reject(new Error("微信登录没有返回凭证")),
      fail: () => reject(new Error("暂时无法连接微信登录"))
    });
  });
}

/** Exchange WeChat identity for the same bearer contract used by legacy sessions. */
async function requestWeChatSession(inviteCode = "") {
  const code = await getWeChatLoginCode();
  let session;
  try {
    session = await request("/customers/wechat-session", {
      method: "POST",
      timeout: 12000,
      data: {
        code,
        invite_code: inviteCode,
        display_name: "女朋友",
        device_label: "微信小程序"
      },
      preserveSession: true
    });
  } catch (error) {
    if (WECHAT_CAPABILITY_FALLBACK_STATUS_CODES.has(error?.statusCode)) {
      markApiCapabilityUnavailable(API_BASE_URL, WECHAT_SESSION_CAPABILITY);
    }
    throw error;
  }
  clearApiCapabilityCooldown(API_BASE_URL, WECHAT_SESSION_CAPABILITY);
  saveCustomerSession(session);
  markWeChatIdentityBound();
  return session;
}

/** Bind a pre-v3 authenticated customer without creating a second identity. */
export async function bindCurrentCustomerToWeChat() {
  if (!hasCustomerSession() || hasWeChatIdentityBinding()) return null;
  if (isApiCapabilityCoolingDown(API_BASE_URL, WECHAT_SESSION_CAPABILITY)) return null;
  return requestWeChatSession();
}

/** Silently restore a previously bound WeChat identity on a new phone. */
export async function restoreWeChatCustomerSession() {
  if (hasCustomerSession()) return { authenticated: true };
  if (isApiCapabilityCoolingDown(API_BASE_URL, WECHAT_SESSION_CAPABILITY)) return null;
  try {
    return await requestWeChatSession();
  } catch (error) {
    console.info("微信身份尚未绑定，将显示邀请码入口", error?.statusCode || error?.message);
    return null;
  }
}

export async function establishCustomerSession(inviteCode) {
  if (hasCustomerSession()) return { authenticated: true };
  try {
    return await requestWeChatSession(inviteCode);
  } catch (error) {
    // Preserve phased-rollout compatibility only when the WeChat capability is
    // absent or unavailable. Validation, conflicts and rate limits must surface.
    if (
      error?.statusCode
      && !WECHAT_CAPABILITY_FALLBACK_STATUS_CODES.has(error.statusCode)
    ) throw error;
  }
  const legacyCustomerId = getLegacyCustomerId();
  const session = await request("/customers/recover", {
    method: "POST",
    data: {
      invite_code: inviteCode,
      legacy_customer_id: legacyCustomerId,
      display_name: "女朋友",
      device_label: "微信小程序"
    },
    preserveSession: true
  });
  saveCustomerSession(session);
  return session;
}

export async function refreshCustomerSession() {
  const session = await request("/customers/refresh", { method: "POST" });
  saveCustomerSession(session);
  return session;
}

export async function revokeCustomerSession() {
  await request("/customers/revoke", { method: "POST", preserveSession: true });
  clearCustomerSession();
}

export const createOrder = (data) =>
  request("/orders", {
    method: "POST",
    data
  });

export const getMyOrders = (customerId) =>
  request("/orders/me");

export const getOrder = (id) => request(`/orders/${id}`);

export const repeatOrder = (orderId, customerId) =>
  request(`/orders/${orderId}/repeat-preview`, {
    method: "POST",
    header: customerHeader(customerId)
  });

export const createReview = (orderId, data) =>
  request(`/orders/${orderId}/review`, {
    method: "POST",
    data
  });

export const createDiceRoom = (inviteCode) =>
  request("/games/dice/rooms", {
    method: "POST",
    data: { invite_code: inviteCode }
  });

export const getGames = () => request("/games", { maxRetries: 0 });

export const createGameRoom = (
  gameType,
  creator,
  inviteCode,
  mode = "couple",
  difficulty = "rule"
) =>
  request("/games/rooms", {
    method: "POST",
    data: {
      game_type: gameType,
      creator,
      mode,
      difficulty,
      invite_code: inviteCode
    }
  });

export const getGameRoom = (roomCode) =>
  request(`/games/rooms/${encodeURIComponent(roomCode)}`);

export const getMyGameRecords = (customerId) =>
  request("/games/records/my", {
    header: customerHeader(customerId)
  });

export const createFlightRoom = (
  customerId,
  playerName,
  inviteCode,
  mode = "couple",
  difficulty = "rule"
) =>
  request("/games/flight/create", {
    method: "POST",
    data: { player_name: playerName, mode, difficulty, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const joinFlightRoom = (customerId, roomCode, playerName, inviteCode) =>
  request("/games/flight/join", {
    method: "POST",
    data: {
      room_code: roomCode,
      player_name: playerName,
      invite_code: inviteCode
    },
    header: customerHeader(customerId)
  });

export const getFlightState = (customerId, roomCode) =>
  request(`/games/flight/${encodeURIComponent(roomCode)}/state`, {
    header: customerHeader(customerId)
  });

export const sendFlightAction = (
  customerId,
  roomCode,
  action,
  pieceIndex,
  expectedVersion,
  clientActionId = createGameActionId("flight")
) =>
  request("/games/flight/action", {
    method: "POST",
    data: {
      room_code: roomCode,
      action,
      client_action_id: clientActionId,
      ...(Number.isInteger(expectedVersion) ? { expected_version: expectedVersion } : {}),
      ...(Number.isInteger(pieceIndex) ? { piece_index: pieceIndex } : {})
    },
    header: customerHeader(customerId)
  });

export const createLandlordRoom = (
  customerId,
  playerName,
  difficulty,
  inviteCode,
  mode = "couple"
) =>
  request("/games/landlord/create", {
    method: "POST",
    data: { player_name: playerName, mode, difficulty, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const joinLandlordRoom = (customerId, roomCode, playerName, inviteCode) =>
  request("/games/landlord/join", {
    method: "POST",
    data: { room_code: roomCode, player_name: playerName, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const sendLandlordAction = (customerId, roomCode, version, action, data = {}, clientActionId = createGameActionId("landlord")) =>
  request("/games/landlord/action", {
    method: "POST",
    data: { room_code: roomCode, expected_version: version, client_action_id: clientActionId, action, ...data },
    header: customerHeader(customerId)
  });

export const createAnimalRoom = (customerId, playerName, mode, difficulty, inviteCode) =>
  request("/games/animal/create", {
    method: "POST",
    data: { player_name: playerName, mode, difficulty, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const joinAnimalRoom = (customerId, roomCode, playerName, inviteCode) =>
  request("/games/animal/join", {
    method: "POST",
    data: { room_code: roomCode, player_name: playerName, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const sendAnimalMove = (customerId, roomCode, version, action, data = {}, clientActionId = createGameActionId("animal")) =>
  request("/games/animal/move", {
    method: "POST",
    data: { room_code: roomCode, expected_version: version, client_action_id: clientActionId, action, ...data },
    header: customerHeader(customerId)
  });

export const createChessRoom = (customerId, playerName, mode, difficulty, inviteCode) =>
  request("/games/chess/create", {
    method: "POST",
    data: { player_name: playerName, mode, difficulty, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const joinChessRoom = (customerId, roomCode, playerName, inviteCode) =>
  request("/games/chess/join", {
    method: "POST",
    data: { room_code: roomCode, player_name: playerName, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const sendChessMove = (customerId, roomCode, version, action, data = {}, clientActionId = createGameActionId("chess")) =>
  request("/games/chess/move", {
    method: "POST",
    data: { room_code: roomCode, expected_version: version, client_action_id: clientActionId, action, ...data },
    header: customerHeader(customerId)
  });

export const getChessHistory = (customerId, gameId) =>
  request(`/games/chess/${gameId}/history`, { header: customerHeader(customerId) });

export const getGameRanking = (customerId) =>
  request("/games/ranking", { header: customerHeader(customerId) });

export const getGameMemories = (customerId) =>
  request("/games/memories/my", { header: customerHeader(customerId) });

export const getGameAIPlayers = () => request("/games/ai/players");

export const getGameAISummary = (customerId) =>
  request("/games/ai/summary", { header: customerHeader(customerId) });

export const getVersionedGameState = (customerId, roomCode) =>
  request(`/games/${encodeURIComponent(roomCode)}/state`, {
    header: customerHeader(customerId)
  });

export const getGameAchievements = (customerId) =>
  request("/games/achievements", { header: customerHeader(customerId) });

export const getMyGameLoveTasks = (customerId) =>
  request("/games/tasks/my", { header: customerHeader(customerId) });

export const completeGameLoveTask = (customerId, taskId) =>
  request(`/games/tasks/${taskId}/complete`, {
    method: "POST",
    header: customerHeader(customerId)
  });

export const getCoupleScore = (customerId) =>
  request("/couple/score", { header: customerHeader(customerId) });

export const getCoupleScoreHistory = (customerId) =>
  request("/couple/score/history", { header: customerHeader(customerId) });

export const getCurrentUser = (customerId) =>
  request("/users/me", { header: customerHeader(customerId) });

export const updateCurrentUser = (customerId, data) =>
  request("/users/me", { method: "PUT", data, header: customerHeader(customerId) });

export const sendPresence = (customerId) =>
  request("/users/presence", { method: "POST", header: customerHeader(customerId) });

export const getNotifications = (customerId, unreadOnly = false) =>
  request("/notifications", {
    data: unreadOnly ? { unread_only: true } : undefined,
    header: customerHeader(customerId)
  });

export const getNotificationUnreadCount = (customerId) =>
  request("/notifications/unread-count", { header: customerHeader(customerId) });

export const markNotificationRead = (customerId, notificationId) =>
  request(`/notifications/${notificationId}/read`, {
    method: "PATCH",
    header: customerHeader(customerId)
  });

export const getCoupleProfile = (customerId) =>
  request("/couple/profile", { header: customerHeader(customerId) });

export const getCoupleStatistics = (customerId) =>
  request("/couple/statistics", { header: customerHeader(customerId) });

export const getCoupleMemories = (customerId) =>
  request("/couple/memories", { header: customerHeader(customerId) });

export const createCoupleMemory = (customerId, data) =>
  request("/couple/memories", { method: "POST", data, header: customerHeader(customerId) });

export const deleteCoupleMemory = (customerId, memoryId) =>
  request(`/couple/memories/${memoryId}`, { method: "DELETE", header: customerHeader(customerId) });

export const getCoupleDates = (customerId) =>
  request("/couple/dates", { header: customerHeader(customerId) });

export const createCoupleDate = (customerId, data) =>
  request("/couple/dates", { method: "POST", data, header: customerHeader(customerId) });

export const deleteCoupleDate = (customerId, dateId) =>
  request(`/couple/dates/${dateId}`, { method: "DELETE", header: customerHeader(customerId) });

export const getActiveGames = (customerId) =>
  request("/games/active", { header: customerHeader(customerId), maxRetries: 0 });

export const issueReconnectToken = (customerId, roomCode) =>
  request("/games/reconnect/token", {
    method: "POST",
    data: { room_code: roomCode },
    header: customerHeader(customerId)
  });

export const reconnectGame = (reconnectToken) =>
  request("/games/reconnect", {
    method: "POST",
    data: { reconnect_token: reconnectToken },
    // An expired room credential is not an expired customer session.  Keep
    // the device login so gameRecovery can rotate the room token safely.
    preserveSession: true
  });

export const getGameReplay = (customerId, recordId) =>
  request(`/games/records/${recordId}/replay`, { header: customerHeader(customerId) });

export const getTodayTasks = (customerId) =>
  request("/couple/tasks/today", { header: customerHeader(customerId) });

export const completeTodayTask = (customerId, taskId) =>
  request(`/couple/tasks/${taskId}/complete`, {
    method: "POST",
    header: customerHeader(customerId)
  });

export const addAdminCoupleScore = (data, customerId, token) =>
  request("/couple/score/add", {
    method: "POST",
    data,
    header: {
      ...customerHeader(customerId),
      Authorization: `Bearer ${token}`
    }
  });

export const adminLogin = (password, inviteCode) =>
  request("/admin/login", {
    method: "POST",
    data: { password, invite_code: inviteCode }
  });

export const getAdminOrderPage = (token, filters = {}) =>
  request("/admin/orders", {
    data: filters,
    header: { Authorization: `Bearer ${token}` }
  });

export const getAdminOrders = async (token) => {
  const page = await getAdminOrderPage(token, { limit: 50 });
  return page.items || [];
};

/** Roll back only the order state the administrator actually saw. */
export const rollbackAdminOrderStatus = (orderId, token, expectedStatus) =>
  request(`/admin/orders/${orderId}/rollback`, {
    method: "POST",
    data: expectedStatus ? { expected_status: expectedStatus } : undefined,
    header: { Authorization: `Bearer ${token}` }
  });

/** Advance an order with an optional stale-page precondition for rolling compatibility. */
export const updateAdminOrderStatus = (orderId, status, token, expectedStatus) =>
  request(`/orders/${orderId}/status`, {
    method: "PATCH",
    data: {
      status,
      ...(expectedStatus ? { expected_status: expectedStatus } : {})
    },
    header: { Authorization: `Bearer ${token}` }
  });

export const createAdminDish = (data, token) =>
  request("/dishes", {
    method: "POST",
    data,
    header: { Authorization: `Bearer ${token}` }
  });

export const updateAdminDish = (dishId, data, token) =>
  request(`/dishes/${dishId}`, {
    method: "PUT",
    data,
    header: { Authorization: `Bearer ${token}` }
  });

export const deleteAdminDish = (dishId, token) =>
  request(`/dishes/${dishId}`, {
    method: "DELETE",
    header: { Authorization: `Bearer ${token}` }
  });

export async function uploadAdminImage(filePath, token) {
  let response;
  try {
    response = await Taro.uploadFile({
      url: `${API_BASE_URL}/upload/image`,
      filePath,
      name: "file",
      timeout: 60000,
      header: { Authorization: `Bearer ${token}` }
    });
  } catch (error) {
    throw new Error(/timeout/i.test(error?.errMsg || "")
      ? "图片上传超时，请稍后重试"
      : "图片上传失败，请检查网络");
  }

  let data = response.data;
  if (typeof data === "string") {
    try {
      data = JSON.parse(data);
    } catch {
      data = {};
    }
  }
  if (response.statusCode >= 200 && response.statusCode < 300 && data?.image_url) {
    return data;
  }
  const detail = data?.detail || "图片上传失败";
  const error = new Error(typeof detail === "string" ? detail : "图片上传失败");
  error.statusCode = response.statusCode;
  throw error;
}

export const getAdminStatsSummary = (token) =>
  request("/stats/summary", {
    header: { Authorization: `Bearer ${token}` }
  });

export const getAdminDishStats = (token) =>
  request("/stats/dishes", {
    header: { Authorization: `Bearer ${token}` }
  });

export const getAdminRecentOrders = (token) =>
  request("/stats/recent", {
    header: { Authorization: `Bearer ${token}` }
  });

export const getAdminGameStats = (token) =>
  request("/admin/games/stats", {
    header: { Authorization: `Bearer ${token}` }
  });

export const getAdminDashboard = (token) =>
  request("/admin/dashboard", {
    header: { Authorization: `Bearer ${token}` }
  });
