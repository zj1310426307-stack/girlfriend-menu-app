import Taro from "@tarojs/taro";

import { request } from "../transport";

const DISH_CACHE_KEY = "gf_dishes_cache_v28";
const DISH_CACHE_TTL = 10 * 60 * 1000;

/** Return cached active dishes while retaining the established offline fallback. */
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

/** Fetch the additive V3 home aggregation and warm the existing dish cache. */
export async function getHomeBootstrap() {
  const payload = await request("/bootstrap");
  if (!Array.isArray(payload?.dishes) || !Array.isArray(payload?.favorite_ranking)) {
    throw new Error("首页数据格式不正确");
  }
  Taro.setStorageSync(DISH_CACHE_KEY, { savedAt: Date.now(), items: payload.dishes });
  return payload;
}

export const getDish = (id) => request(`/dishes/${id}`);
export const getFavorites = () => request("/favorites");
export const addFavorite = (dishId) => request(`/favorites/${dishId}`, { method: "POST" });
export const removeFavorite = (dishId) => request(`/favorites/${dishId}`, { method: "DELETE" });
export const getFavoriteRanking = () => request("/stats/favorite-ranking");
