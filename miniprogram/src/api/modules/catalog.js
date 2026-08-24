import Taro from "@tarojs/taro";

import { request } from "../transport";
import { getAuthenticatedCustomerId } from "../../utils/customer";
import { writeHomeSnapshot } from "../../utils/homeSnapshot";

const DISH_CACHE_KEY = "gf_dishes_cache_v28";
const DISH_CACHE_TTL = 10 * 60 * 1000;
export const DISH_CACHE_MAX_AGE = 7 * 24 * 60 * 60 * 1000;

/** Read cached public menu data synchronously so the first render never waits on a Promise. */
export function getCachedDishes({ maxAge = DISH_CACHE_TTL } = {}) {
  try {
    const cached = Taro.getStorageSync(DISH_CACHE_KEY);
    const age = Date.now() - Number(cached?.savedAt);
    if (!Array.isArray(cached?.items) || !Number.isFinite(age) || age < 0 || age > maxAge) return [];
    return cached.items;
  } catch (error) {
    console.info("菜单缓存读取失败，将使用在线数据", error?.message);
    return [];
  }
}

/** Warm the public menu cache without turning a storage quota issue into a request failure. */
function cacheDishes(items) {
  try {
    Taro.setStorageSync(DISH_CACHE_KEY, { savedAt: Date.now(), items });
  } catch (error) {
    console.info("菜单缓存保存失败，本次访问不受影响", error?.message);
  }
}

/** Return cached active dishes while retaining the established offline fallback. */
export async function getDishes(category, { force = false } = {}) {
  let cached;
  try {
    cached = Taro.getStorageSync(DISH_CACHE_KEY);
  } catch (error) {
    console.info("菜单缓存读取失败，将使用在线数据", error?.message);
  }
  const fresh = cached?.savedAt && Date.now() - cached.savedAt < DISH_CACHE_TTL;
  if (!force && fresh && Array.isArray(cached.items)) {
    return category ? cached.items.filter((dish) => dish.category === category) : cached.items;
  }
  try {
    const items = await request("/dishes");
    cacheDishes(items);
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
  const payload = await request("/bootstrap", { timeout: 12000, maxRetries: 0 });
  if (
    !Array.isArray(payload?.dishes)
    || !Array.isArray(payload?.favorite_ranking)
    || !Array.isArray(payload?.today_tasks?.tasks)
    || !("recent_order" in payload)
  ) {
    const error = new Error("首页数据格式不正确");
    error.code = "BOOTSTRAP_SCHEMA_MISMATCH";
    throw error;
  }
  cacheDishes(payload.dishes);
  writeHomeSnapshot(getAuthenticatedCustomerId(), payload);
  return payload;
}

export const getDish = (id) => request(`/dishes/${id}`);
export const getFavorites = () => request("/favorites");
export const addFavorite = (dishId) => request(`/favorites/${dishId}`, { method: "POST" });
export const removeFavorite = (dishId) => request(`/favorites/${dishId}`, { method: "DELETE" });
export const getFavoriteRanking = () => request("/stats/favorite-ranking");
