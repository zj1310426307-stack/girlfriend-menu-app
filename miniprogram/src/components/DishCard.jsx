import { useState } from "react";
import { Image, Text, View } from "@tarojs/components";

import { resolveImageUrl } from "../api";
import "./DishCard.css";

/**
 * Shared customer-facing dish card used by home and menu pages.
 * Optional actions stay hidden when a parent page does not need them.
 */
export default function DishCard({
  dish,
  compact = false,
  favorite = false,
  favoriteBusy = false,
  onOpen,
  onAdd,
  onToggleFavorite
}) {
  const [imageFailed, setImageFailed] = useState(false);

  const stopAndRun = (event, callback) => {
    event?.stopPropagation?.();
    callback?.(dish);
  };

  return (
    <View className={`shared-dish-card ${compact ? "is-compact" : ""}`} onClick={() => onOpen?.(dish)}>
      {dish.image_url && !imageFailed ? (
        <Image
          className="shared-dish-image"
          src={resolveImageUrl(dish.image_url, { maxWidth: compact ? 640 : 480 })}
          mode="aspectFill"
          lazyLoad
          onError={() => setImageFailed(true)}
        />
      ) : (
        <View className="shared-dish-placeholder"><Text>今日小菜</Text></View>
      )}

      <View className="shared-dish-body">
        <View className="shared-dish-heading">
          <View>
            <Text className="shared-dish-name">{dish.name}</Text>
            <Text className="shared-dish-category">{dish.category}</Text>
          </View>
          {onToggleFavorite && (
            <View
              className={`shared-favorite-button ${favorite ? "is-favorite" : ""} ${favoriteBusy ? "is-busy" : ""}`}
              onClick={(event) => {
                event?.stopPropagation?.();
                if (!favoriteBusy) onToggleFavorite(dish);
              }}
            >
              <Text>{favoriteBusy ? "…" : favorite ? "♥" : "♡"}</Text>
            </View>
          )}
        </View>

        {!compact && (
          <Text className="shared-dish-description">
            {dish.description || "今天也很适合吃这道菜。"}
          </Text>
        )}

        <View className="shared-dish-meta">
          {dish.cook_time ? <Text>约 {dish.cook_time} 分钟</Text> : <Text>认真准备</Text>}
          {dish.spicy_level > 0 && <Text>{"辣".repeat(Math.min(3, dish.spicy_level))}</Text>}
        </View>

        {Array.isArray(dish.tags) && dish.tags.length > 0 && (
          <View className="shared-dish-tags">
            {dish.tags.slice(0, 3).map((tag) => <Text key={tag}>#{tag}</Text>)}
          </View>
        )}

        <View className="shared-dish-footer">
          <Text className="shared-dish-price">¥{Number(dish.price).toFixed(2)}</Text>
          {onAdd && (
            <View className="shared-add-button" onClick={(event) => stopAndRun(event, onAdd)}>
              <Text>+</Text>
            </View>
          )}
        </View>
      </View>
    </View>
  );
}
