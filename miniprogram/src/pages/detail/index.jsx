import { useState } from "react";
import Taro, { useLoad } from "@tarojs/taro";
import { Image, Text, View } from "@tarojs/components";

import { getDish, resolveImageUrl } from "../../api";
import { addToCart } from "../../utils/cart";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

export default function Detail() {
  const [dish, setDish] = useState(null);
  const [error, setError] = useState("");

  useLoad((params) => {
    if (!ensureInvitePassed()) return;
    getDish(params.id)
      .then(setDish)
      .catch((err) => setError(err.message || "没有找到这道菜"));
  });

  const addDish = () => {
    addToCart(dish);
    Taro.showToast({ title: "已加入点菜清单", icon: "success" });
  };

  if (error) return <View className="page"><View className="state-box error">{error}</View></View>;
  if (!dish) return <View className="page"><View className="state-box">正在端上这道菜…</View></View>;

  return (
    <View className="page detail-page">
      {dish.image_url ? (
        <Image className="detail-image" src={resolveImageUrl(dish.image_url)} mode="aspectFill" />
      ) : (
        <View className="detail-placeholder">🍲</View>
      )}

      <View className="detail-card card">
        <Text className="dish-category">{dish.category}</Text>
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
