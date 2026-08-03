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
