import { useMemo, useRef, useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Input, ScrollView, Text, View } from "@tarojs/components";

import {
  addFavorite,
  DISH_CACHE_MAX_AGE,
  getCachedDishes,
  getDishes,
  getFavorites,
  removeFavorite
} from "../../api";
import DishCard from "../../components/DishCard";
import AsyncState from "../../components/AsyncState";
import PageSyncNotice from "../../components/PageSyncNotice";
import { addToCart, getCart } from "../../utils/cart";
import { ensureInvitePassed } from "../../utils/invite";
import { getAuthenticatedCustomerId, getCustomerId, hasCustomerSession } from "../../utils/customer";
import {
  claimPageRefresh,
  PAGE_SNAPSHOT_MAX_AGE,
  readPageSnapshot,
  releasePageRefresh,
  writePageSnapshot
} from "../../utils/pageSnapshot";
import "./index.css";

/** Hydrate public dishes and the current customer's favorite IDs before first paint. */
function createInitialMenuState() {
  if (!hasCustomerSession()) return { dishes: [], favoriteIds: [], hasSnapshot: false };
  const customerId = getAuthenticatedCustomerId();
  const snapshot = readPageSnapshot("menu", customerId, PAGE_SNAPSHOT_MAX_AGE.menu);
  const dishes = getCachedDishes({ maxAge: DISH_CACHE_MAX_AGE });
  return {
    dishes,
    favoriteIds: Array.isArray(snapshot?.favoriteIds) ? snapshot.favoriteIds : [],
    hasSnapshot: Boolean(snapshot || dishes.length)
  };
}

/** Full menu owns search and category filtering after the V2 home split. */
export default function MenuPage() {
  const [initialMenu] = useState(createInitialMenuState);
  const [dishes, setDishes] = useState(initialMenu.dishes);
  const [category, setCategory] = useState("全部");
  const [query, setQuery] = useState("");
  const [cartCount, setCartCount] = useState(0);
  const [loading, setLoading] = useState(!initialMenu.hasSnapshot);
  const [hasLoaded, setHasLoaded] = useState(initialMenu.hasSnapshot);
  const [error, setError] = useState("");
  const [favoriteIds, setFavoriteIds] = useState(initialMenu.favoriteIds);
  const [favoriteUpdatingIds, setFavoriteUpdatingIds] = useState([]);
  const favoriteIdsRef = useRef(initialMenu.favoriteIds);
  const favoriteMutationVersionRef = useRef(0);
  const favoriteUpdatingRef = useRef(new Set());
  const menuLoadingRef = useRef(false);

  const commitFavoriteIds = (nextFavoriteIds) => {
    favoriteIdsRef.current = nextFavoriteIds;
    setFavoriteIds(nextFavoriteIds);
  };

  /** Refresh dishes and favorites once while leaving hydrated content interactive. */
  const load = async ({ force = false } = {}) => {
    if (!ensureInvitePassed()) return;
    if (menuLoadingRef.current) return;
    const customerId = getCustomerId();
    if (!claimPageRefresh("menu", customerId, { force })) return;
    menuLoadingRef.current = true;
    setCartCount(getCart().reduce((total, item) => total + item.quantity, 0));
    setLoading(true);
    setError("");
    const favoriteMutationVersion = favoriteMutationVersionRef.current;
    try {
      const [dishResult, favoriteResult] = await Promise.allSettled([
        getDishes(),
        getFavorites(customerId)
      ]);
      if (dishResult.status === "rejected") throw dishResult.reason;
      setDishes(dishResult.value);
      setHasLoaded(true);
      const favoriteRefreshIsCurrent = favoriteResult.status === "fulfilled"
        && favoriteMutationVersion === favoriteMutationVersionRef.current
        && favoriteUpdatingRef.current.size === 0;
      if (favoriteRefreshIsCurrent) {
        const nextFavoriteIds = favoriteResult.value.map((dish) => dish.id);
        commitFavoriteIds(nextFavoriteIds);
        writePageSnapshot("menu", customerId, { favoriteIds: nextFavoriteIds });
      } else if (favoriteResult.status === "rejected") {
        releasePageRefresh("menu", customerId);
        setError(favoriteResult.reason?.message || "收藏状态暂时没有同步");
      }
    } catch (requestError) {
      releasePageRefresh("menu", customerId);
      setError(requestError.message || "菜单加载失败");
    } finally {
      setLoading(false);
      menuLoadingRef.current = false;
    }
  };

  useDidShow(load);

  const categories = useMemo(() => ["全部", ...new Set(dishes.map((dish) => dish.category))], [dishes]);
  const visibleDishes = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return dishes.filter((dish) => {
      const categoryMatches = category === "全部" || dish.category === category;
      const text = `${dish.name} ${dish.description || ""} ${(dish.tags || []).join(" ")}`.toLowerCase();
      return categoryMatches && (!keyword || text.includes(keyword));
    });
  }, [category, dishes, query]);

  const addDish = (dish) => {
    const next = addToCart(dish);
    setCartCount(next.reduce((total, item) => total + item.quantity, 0));
    Taro.vibrateShort({ type: "light" }).catch(() => {});
    Taro.showToast({ title: "已放进点菜单", icon: "success" });
  };

  const toggleFavorite = async (dish) => {
    // Keep one authoritative favorite mutation per dish while the network is in flight.
    if (favoriteUpdatingRef.current.has(dish.id)) return;
    favoriteUpdatingRef.current.add(dish.id);
    favoriteMutationVersionRef.current += 1;
    setFavoriteUpdatingIds((current) => [...current, dish.id]);
    const isFavorite = favoriteIdsRef.current.includes(dish.id);
    const customerId = getCustomerId();
    const optimisticIds = isFavorite
      ? favoriteIdsRef.current.filter((id) => id !== dish.id)
      : [...favoriteIdsRef.current, dish.id];
    try {
      commitFavoriteIds(optimisticIds);
      writePageSnapshot("menu", customerId, { favoriteIds: optimisticIds });
      if (isFavorite) await removeFavorite(dish.id, customerId);
      else await addFavorite(dish.id, customerId);
      Taro.showToast({ title: isFavorite ? "已取消收藏" : "已收藏", icon: "success" });
    } catch (requestError) {
      const current = favoriteIdsRef.current;
      const restored = isFavorite
        ? current.includes(dish.id) ? current : [...current, dish.id]
        : current.filter((id) => id !== dish.id);
      commitFavoriteIds(restored);
      writePageSnapshot("menu", customerId, { favoriteIds: restored });
      Taro.showToast({ title: requestError.message || "收藏操作失败", icon: "none" });
    } finally {
      favoriteUpdatingRef.current.delete(dish.id);
      favoriteMutationVersionRef.current += 1;
      setFavoriteUpdatingIds((current) => current.filter((id) => id !== dish.id));
    }
  };

  return (
    <View className="page v2-menu-page">
      <View className="v2-menu-heading">
        <Text className="eyebrow">OUR MENU</Text>
        <Text>慢慢挑，想吃的都可以说</Text>
        <Text>{dishes.length} 道菜正在菜单里</Text>
      </View>
      <Input className="v2-menu-search" value={query} placeholder="搜索菜名、口味或标签" onInput={(event) => setQuery(event.detail.value)} />
      <ScrollView className="v2-category-tabs" scrollX enhanced showScrollbar={false}>
        <View className="v2-category-tabs-track">
          {categories.map((item) => (
            <View key={item} className={category === item ? "active" : ""} onClick={() => setCategory(item)}><Text>{item}</Text></View>
          ))}
        </View>
      </ScrollView>
      {hasLoaded && <PageSyncNotice loading={loading} offline={Boolean(error)} onRetry={() => load({ force: true })} />}
      {loading && !hasLoaded && <AsyncState message="正在翻开菜单…" />}
      {error && !hasLoaded && <AsyncState type="error" message={error} onRetry={() => load({ force: true })} />}
      {!loading && !error && hasLoaded && visibleDishes.length === 0 && <AsyncState type="empty" message="没有找到这道菜，换个词试试吧" />}
      <View className="v2-menu-list">
        {visibleDishes.map((dish) => (
          <DishCard
            key={dish.id}
            dish={dish}
            favorite={favoriteIds.includes(dish.id)}
            favoriteBusy={favoriteUpdatingIds.includes(dish.id)}
            onOpen={() => Taro.navigateTo({ url: `/pages/detail/index?id=${dish.id}` })}
            onAdd={addDish}
            onToggleFavorite={toggleFavorite}
          />
        ))}
      </View>
      {cartCount > 0 && (
        <View className="v2-cart-bar" onClick={() => Taro.navigateTo({ url: "/pages/cart/index" })}>
          <Text>{cartCount} 份已选</Text><Text>查看点菜单</Text>
        </View>
      )}
    </View>
  );
}
