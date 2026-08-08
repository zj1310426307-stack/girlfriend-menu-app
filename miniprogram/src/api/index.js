import Taro from "@tarojs/taro";

export const API_BASE_URL = "https://girlfriend-menu-api.onrender.com/api";
const API_ORIGIN = "https://girlfriend-menu-api.onrender.com";
const REQUEST_TIMEOUT = 45000;
const MAX_GET_RETRIES = 2;
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);

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
    const error = new Error(typeof detail === "string" ? detail : "请求参数不正确");
    error.statusCode = response.statusCode;
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

export const getDishes = (category) =>
  request("/dishes", {
    data: category ? { category } : undefined
  });

export const getDish = (id) => request(`/dishes/${id}`);

export const createOrder = (data) =>
  request("/orders", {
    method: "POST",
    data
  });

export const getMyOrders = (customerId) =>
  request(`/orders/my/${encodeURIComponent(customerId)}`);

export const getOrder = (id) => request(`/orders/${id}`);

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

export const adminLogin = (password, inviteCode) =>
  request("/admin/login", {
    method: "POST",
    data: { password, invite_code: inviteCode }
  });

export const getAdminOrders = (token) =>
  request("/orders", {
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
