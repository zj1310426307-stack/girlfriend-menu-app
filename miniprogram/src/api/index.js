import Taro from "@tarojs/taro";

export const API_BASE_URL = "https://girlfriend-menu-api.onrender.com/api";
const API_ORIGIN = "https://girlfriend-menu-api.onrender.com";

function normalizePath(path) {
  return path.startsWith("/") ? path : `/${path}`;
}

function request(path, options = {}) {
  return Taro.request({
    url: `${API_BASE_URL}${normalizePath(path)}`,
    method: options.method || "GET",
    data: options.data,
    header: {
      "content-type": "application/json",
      ...(options.header || {})
    }
  }).then((response) => {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.data;
    }
    const detail = response.data?.detail || "请求失败，请稍后再试";
    return Promise.reject(new Error(detail));
  });
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
