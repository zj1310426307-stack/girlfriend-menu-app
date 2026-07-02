import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api";

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 10000,
});

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

api.interceptors.response.use(
  (response) => response,
  (error) => {
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

export const adminLogin = (password) =>
  api.post("/admin/login", { password }).then((res) => res.data);
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
