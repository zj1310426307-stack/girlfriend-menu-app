import { useState } from "react";
import Taro, { useLoad } from "@tarojs/taro";
import { Image, Text, View } from "@tarojs/components";

import { addFavorite, getDish, getFavorites, removeFavorite, resolveImageUrl } from "../../api";
import { addToCart } from "../../utils/cart";
import { ensureInvitePassed } from "../../utils/invite";
import { getCustomerId } from "../../utils/customer";
import "./index.css";

export default function Detail() {
  const [dish, setDish] = useState(null);
  const [error, setError] = useState("");
  const [dishId, setDishId] = useState("");
  const [imageFailed, setImageFailed] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);

  const loadDish = (id) => {
    if (!id) return;
    setError("");
    Promise.all([
      getDish(id),
      getFavorites(getCustomerId()).catch(() => [])
    ])
      .then(([nextDish, favorites]) => {
        setDish(nextDish);
        setFavorite(favorites.some((item) => item.id === nextDish.id));
      })
      .catch((err) => setError(err.message || "没有找到这道菜"));
  };

  useLoad((params) => {
    if (!ensureInvitePassed()) return;
    setDishId(params.id);
    loadDish(params.id);
  });

  const addDish = () => {
    addToCart(dish);
    Taro.showToast({ title: "已加入点菜清单", icon: "success" });
  };

  const toggleFavorite = async () => {
    if (savingFavorite) return;
    setSavingFavorite(true);
    const nextValue = !favorite;
    setFavorite(nextValue);
    try {
      if (nextValue) await addFavorite(dish.id, getCustomerId());
      else await removeFavorite(dish.id, getCustomerId());
      Taro.showToast({ title: nextValue ? "已经收藏啦" : "已取消收藏", icon: "success" });
    } catch (requestError) {
      setFavorite(!nextValue);
      Taro.showToast({ title: requestError.message || "收藏操作失败", icon: "none" });
    } finally {
      setSavingFavorite(false);
    }
  };

  if (error) {
    return (
      <View className="page">
        <View className="state-box error">
          <Text>{error}</Text>
          <View className="retry-button" onClick={() => loadDish(dishId)}><Text>重新加载</Text></View>
        </View>
      </View>
    );
  }
  if (!dish) return <View className="page"><View className="state-box">正在端上这道菜…</View></View>;

  return (
    <View className="page detail-page">
      {dish.image_url && !imageFailed ? (
        <Image
          className="detail-image"
          src={resolveImageUrl(dish.image_url)}
          mode="aspectFill"
          onError={() => setImageFailed(true)}
        />
      ) : (
        <View className="detail-placeholder">🍲</View>
      )}

      <View className="detail-card card">
        <View className="detail-heading-row">
          <Text className="dish-category">{dish.category}</Text>
          <View className={`detail-favorite ${favorite ? "active" : ""}`} onClick={toggleFavorite}>
            <Text>{favorite ? "♥ 已收藏" : "♡ 收藏"}</Text>
          </View>
        </View>
        <Text className="detail-title">{dish.name}</Text>
        <Text className="detail-desc">{dish.description || "今天也很适合吃这道菜。"}</Text>
        <View className="detail-action">
          <Text className="detail-price">¥{Number(dish.price).toFixed(2)}</Text>
          <View className="primary-button detail-button" onClick={addDish}>
            <Text>加入点菜清单</Text>
          </View>
        </View>
      </View>

      <View className="secondary-button detail-cart" onClick={() => Taro.navigateTo({ url: "/pages/cart/index" })}>
        <Text>查看点菜清单</Text>
      </View>
    </View>
  );
}
