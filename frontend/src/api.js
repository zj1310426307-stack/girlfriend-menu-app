import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api";

const api = axios.create({
  baseURL: apiBaseUrl,
  // Render free services can need tens of seconds to wake from sleep.
  timeout: 45000,
});

const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export function getApiErrorMessage(error, fallback = "请求失败，请稍后再试。") {
  if (error?.code === "ECONNABORTED") return "服务器正在醒来，请稍后重试。";
  if (!error?.response) return "网络连接不稳定，请检查网络后重试。";
  const detail = error.response.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  return fallback;
}

export function resolveImageUrl(imageUrl) {
  if (!imageUrl || /^(https?:|data:|blob:)/i.test(imageUrl)) return imageUrl;
  if (!/^https?:\/\//i.test(apiBaseUrl)) return imageUrl;

  try {
    const backendOrigin = new URL(apiBaseUrl).origin;
    return new URL(imageUrl, `${backendOrigin}/`).href;
  } catch {
    return imageUrl;
  }
}

function websocketUrl(path) {
  const url = new URL(apiBaseUrl, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  const rootPath = url.pathname.replace(/\/api\/?$/, "").replace(/\/$/, "");
  url.pathname = `${rootPath}${path}`;
  url.search = "";
  return url.href;
}

export function subscribeToAdminOrderEvents({ onEvent, onStatus }) {
  let socket;
  let reconnectTimer;
  let heartbeatTimer;
  let stopped = false;

  const connect = () => {
    const token = localStorage.getItem("admin_token");
    if (stopped || !token) return;
    onStatus?.("connecting");
    socket = new WebSocket(websocketUrl("/ws/admin/orders"));
    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ type: "auth", token }));
    });
    socket.addEventListener("message", (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "ready") {
          onStatus?.("online");
          clearInterval(heartbeatTimer);
          heartbeatTimer = setInterval(() => {
            if (socket?.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: "ping" }));
            }
          }, 25000);
        } else if (message.type === "error") {
          onStatus?.("error");
        } else {
          onEvent?.(message);
        }
      } catch {
        // Ignore malformed messages and keep the live connection running.
      }
    });
    socket.addEventListener("close", () => {
      clearInterval(heartbeatTimer);
      onStatus?.("offline");
      if (!stopped) reconnectTimer = setTimeout(connect, 2500);
    });
    socket.addEventListener("error", () => onStatus?.("offline"));
  };

  connect();
  return () => {
    stopped = true;
    clearTimeout(reconnectTimer);
    clearInterval(heartbeatTimer);
    socket?.close();
  };
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config || {};
    const method = String(config.method || "get").toLowerCase();
    const responseStatus = error.response?.status;
    const shouldRetry =
      ["get", "head"].includes(method)
      && (responseStatus == null || RETRYABLE_STATUS.has(responseStatus))
      && (config.__retryCount || 0) < 2;

    if (shouldRetry) {
      config.__retryCount = (config.__retryCount || 0) + 1;
      await sleep(config.__retryCount * 700);
      return api(config);
    }

    const isLoginRequest = error.config?.url === "/admin/login";
    if (
      error.response?.status === 401
      && !isLoginRequest
      && localStorage.getItem("admin_token")
    ) {
      localStorage.removeItem("admin_token");
      if (window.location.pathname.startsWith("/admin")) {
        window.location.replace("/admin/login");
      }
    }
    return Promise.reject(error);
  },
);

const adminConfig = () => {
  const token = localStorage.getItem("admin_token");
  return token ? { headers: { Authorization: `Bearer ${token}` } } : {};
};

export const adminLogin = ({ password, inviteCode }) =>
  api.post("/admin/login", { password, invite_code: inviteCode }).then((res) => res.data);
export const getDishes = (category) =>
  api.get("/dishes", { params: category ? { category } : {} }).then((res) => res.data);
export const getDish = (id) => api.get(`/dishes/${id}`).then((res) => res.data);
export const createDish = (data) => api.post("/dishes", data, adminConfig()).then((res) => res.data);
export const updateDish = (id, data) =>
  api.put(`/dishes/${id}`, data, adminConfig()).then((res) => res.data);
export const deleteDish = (id) => api.delete(`/dishes/${id}`, adminConfig());
export const uploadImage = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/upload/image", formData, adminConfig()).then((res) => res.data);
};
export const createOrder = (data) => api.post("/orders", data).then((res) => res.data);
export const getOrder = (id) => api.get(`/orders/${id}`).then((res) => res.data);
export const getMyOrders = (customerId) =>
  api.get(`/orders/my/${encodeURIComponent(customerId)}`).then((res) => res.data);
export const getOrders = () => api.get("/orders", adminConfig()).then((res) => res.data);
export const updateOrderStatus = (id, status) =>
  api.patch(`/orders/${id}/status`, { status }, adminConfig()).then((res) => res.data);
export const createReview = (orderId, data) =>
  api.post(`/orders/${orderId}/review`, data).then((res) => res.data);
export const getReview = (orderId) =>
  api.get(`/orders/${orderId}/review`).then((res) => res.data);
export const getStatsSummary = () =>
  api.get("/stats/summary", adminConfig()).then((res) => res.data);
export const getDishStats = () =>
  api.get("/stats/dishes", adminConfig()).then((res) => res.data);
export const getRecentStats = () =>
  api.get("/stats/recent", adminConfig()).then((res) => res.data);

export default api;
