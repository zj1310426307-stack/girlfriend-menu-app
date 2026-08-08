import { useMemo, useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Input, ScrollView, Text, View } from "@tarojs/components";

import { getDishes } from "../../api";
import DishCard from "../../components/DishCard";
import { addToCart, getCart } from "../../utils/cart";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

/** Full menu owns search and category filtering after the V2 home split. */
export default function MenuPage() {
  const [dishes, setDishes] = useState([]);
  const [category, setCategory] = useState("全部");
  const [query, setQuery] = useState("");
  const [cartCount, setCartCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    if (!ensureInvitePassed()) return;
    setCartCount(getCart().reduce((total, item) => total + item.quantity, 0));
    setLoading(true);
    getDishes()
      .then((next) => { setDishes(next); setError(""); })
      .catch((requestError) => setError(requestError.message || "菜单加载失败"))
      .finally(() => setLoading(false));
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

  return (
    <View className="page v2-menu-page">
      <View className="v2-menu-heading">
        <Text className="eyebrow">OUR MENU</Text>
        <Text>慢慢挑，想吃的都可以说</Text>
        <Text>{dishes.length} 道菜正在菜单里</Text>
      </View>
      <Input className="v2-menu-search" value={query} placeholder="搜索菜名、口味或标签" onInput={(event) => setQuery(event.detail.value)} />
      <ScrollView className="v2-category-tabs" scrollX enhanced showScrollbar={false}>
        {categories.map((item) => (
          <View key={item} className={category === item ? "active" : ""} onClick={() => setCategory(item)}><Text>{item}</Text></View>
        ))}
      </ScrollView>
      {loading && <View className="state-box"><Text>正在翻开菜单…</Text></View>}
      {error && <View className="state-box error" onClick={load}><Text>{error}，点这里重试</Text></View>}
      {!loading && !error && visibleDishes.length === 0 && <View className="state-box"><Text>没有找到这道菜，换个词试试吧</Text></View>}
      <View className="v2-menu-list">
        {visibleDishes.map((dish) => (
          <DishCard
            key={dish.id}
            dish={dish}
            onOpen={() => Taro.navigateTo({ url: `/pages/detail/index?id=${dish.id}` })}
            onAdd={addDish}
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
