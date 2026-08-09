import Taro from "@tarojs/taro";
import { API_BASE_URL, API_ORIGIN } from "../config/env";
import {
  getCustomerToken,
  clearCustomerSession,
  getLegacyCustomerId,
  hasCustomerSession,
  saveCustomerSession
} from "../utils/customer";

export { API_BASE_URL };
const REQUEST_TIMEOUT = 45000;
const MAX_GET_RETRIES = 2;
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);
const DISH_CACHE_KEY = "gf_dishes_cache_v28";
const DISH_CACHE_TTL = 10 * 60 * 1000;

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function normalizePath(path) {
  return path.startsWith("/") ? path : `/${path}`;
}

async function request(path, options = {}, attempt = 0) {
  const method = options.method || "GET";
  try {
    const response = await Taro.request({
      url: `${API_BASE_URL}${normalizePath(path)}`,
      method,
      timeout: options.timeout || REQUEST_TIMEOUT,
      data: options.data,
      header: {
        accept: "application/json",
        "content-type": "application/json",
        ...(getCustomerToken() ? { Authorization: `Bearer ${getCustomerToken()}` } : {}),
        ...(options.header || {})
      }
    });
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.data;
    }
    if (
      method === "GET"
      && RETRYABLE_STATUS.has(response.statusCode)
      && attempt < MAX_GET_RETRIES
    ) {
      await wait((attempt + 1) * 700);
      return request(path, options, attempt + 1);
    }
    const detail = response.data?.detail || "请求失败，请稍后再试";
    const message = typeof detail === "string" ? detail : detail?.message || "请求参数不正确";
    const error = new Error(message);
    error.statusCode = response.statusCode;
    if (response.statusCode === 401 && !options.header?.Authorization && getCustomerToken()) {
      clearCustomerSession();
    }
    if (detail?.current_version) error.currentVersion = detail.current_version;
    throw error;
  } catch (error) {
    if (method === "GET" && !error?.statusCode && attempt < MAX_GET_RETRIES) {
      await wait((attempt + 1) * 700);
      return request(path, options, attempt + 1);
    }
    if (!error?.statusCode && /timeout/i.test(error?.errMsg || error?.message || "")) {
      throw new Error("服务器正在醒来，请稍后重试");
    }
    if (
      !error?.statusCode
      && (!error?.message || /request:fail|network/i.test(error?.errMsg || error?.message || ""))
    ) {
      throw new Error("网络连接不稳定，请检查网络后重试");
    }
    throw error;
  }
}

export function resolveImageUrl(imageUrl) {
  if (!imageUrl) return "";
  if (/^(https?:|data:|blob:)/i.test(imageUrl)) return imageUrl;
  return `${API_ORIGIN}${imageUrl.startsWith("/") ? imageUrl : `/${imageUrl}`}`;
}

export async function getDishes(category, { force = false } = {}) {
  const cached = Taro.getStorageSync(DISH_CACHE_KEY);
  const fresh = cached?.savedAt && Date.now() - cached.savedAt < DISH_CACHE_TTL;
  if (!force && fresh && Array.isArray(cached.items)) {
    return category ? cached.items.filter((dish) => dish.category === category) : cached.items;
  }
  try {
    const items = await request("/dishes");
    Taro.setStorageSync(DISH_CACHE_KEY, { savedAt: Date.now(), items });
    return category ? items.filter((dish) => dish.category === category) : items;
  } catch (error) {
    if (Array.isArray(cached?.items)) {
      return category ? cached.items.filter((dish) => dish.category === category) : cached.items;
    }
    throw error;
  }
}

export const getDish = (id) => request(`/dishes/${id}`);

const customerHeader = () => ({});

export async function establishCustomerSession(inviteCode) {
  if (hasCustomerSession()) return { authenticated: true };
  const legacyCustomerId = getLegacyCustomerId();
  const session = await request("/customers/claim-legacy", {
    method: "POST",
    data: { invite_code: inviteCode, legacy_customer_id: legacyCustomerId, display_name: "女朋友" }
  });
  saveCustomerSession(session);
  return session;
}

export async function refreshCustomerSession() {
  const session = await request("/customers/refresh", { method: "POST" });
  saveCustomerSession(session);
  return session;
}

export const getFavorites = (customerId) =>
  request("/favorites", { header: customerHeader(customerId) });

export const addFavorite = (dishId, customerId) =>
  request(`/favorites/${dishId}`, {
    method: "POST",
    header: customerHeader(customerId)
  });

export const removeFavorite = (dishId, customerId) =>
  request(`/favorites/${dishId}`, {
    method: "DELETE",
    header: customerHeader(customerId)
  });

export const getFavoriteRanking = (customerId) =>
  request("/stats/favorite-ranking", {
    header: customerHeader(customerId)
  });

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

export const getGames = () => request("/games");

export const createGameRoom = (gameType, creator, inviteCode) =>
  request("/games/rooms", {
    method: "POST",
    data: {
      game_type: gameType,
      creator,
      invite_code: inviteCode
    }
  });

export const getGameRoom = (roomCode) =>
  request(`/games/rooms/${encodeURIComponent(roomCode)}`);

export const getMyGameRecords = (customerId) =>
  request("/games/records/my", {
    header: customerHeader(customerId)
  });

export const createFlightRoom = (customerId, playerName, inviteCode) =>
  request("/games/flight/create", {
    method: "POST",
    data: { player_name: playerName, invite_code: inviteCode },
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

export const sendFlightAction = (customerId, roomCode, action, pieceIndex) =>
  request("/games/flight/action", {
    method: "POST",
    data: {
      room_code: roomCode,
      action,
      ...(Number.isInteger(pieceIndex) ? { piece_index: pieceIndex } : {})
    },
    header: customerHeader(customerId)
  });

export const createLandlordRoom = (customerId, playerName, difficulty, inviteCode) =>
  request("/games/landlord/create", {
    method: "POST",
    data: { player_name: playerName, difficulty, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const joinLandlordRoom = (customerId, roomCode, playerName, inviteCode) =>
  request("/games/landlord/join", {
    method: "POST",
    data: { room_code: roomCode, player_name: playerName, invite_code: inviteCode },
    header: customerHeader(customerId)
  });

export const sendLandlordAction = (customerId, roomCode, version, action, data = {}) =>
  request("/games/landlord/action", {
    method: "POST",
    data: { room_code: roomCode, expected_version: version, action, ...data },
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

export const sendAnimalMove = (customerId, roomCode, version, action, data = {}) =>
  request("/games/animal/move", {
    method: "POST",
    data: { room_code: roomCode, expected_version: version, action, ...data },
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

export const sendChessMove = (customerId, roomCode, version, action, data = {}) =>
  request("/games/chess/move", {
    method: "POST",
    data: { room_code: roomCode, expected_version: version, action, ...data },
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
  request("/games/active", { header: customerHeader(customerId) });

export const issueReconnectToken = (customerId, roomCode) =>
  request("/games/reconnect/token", {
    method: "POST",
    data: { room_code: roomCode },
    header: customerHeader(customerId)
  });

export const reconnectGame = (reconnectToken) =>
  request("/games/reconnect", { method: "POST", data: { reconnect_token: reconnectToken } });

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

export const rollbackAdminOrderStatus = (orderId, token) =>
  request(`/admin/orders/${orderId}/rollback`, {
    method: "POST",
    header: { Authorization: `Bearer ${token}` }
  });

export const updateAdminOrderStatus = (orderId, status, token) =>
  request(`/orders/${orderId}/status`, {
    method: "PATCH",
    data: { status },
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
