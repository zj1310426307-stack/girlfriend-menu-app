import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getMyOrders, repeatOrder } from "../../api";
import { replaceCart, saveRepeatDraft } from "../../utils/cart";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { formatTime, reviewHint, STATUS_TEXT } from "../../utils/status";
import AsyncState from "../../components/AsyncState";
import "./index.css";

export default function MyOrders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [repeatingId, setRepeatingId] = useState(null);

  const loadOrders = () => {
    if (!ensureInvitePassed()) return;
    setLoading(true);
    setError("");
    getMyOrders(getCustomerId())
      .then(setOrders)
      .catch((err) => setError(err.message || "历史点菜单加载失败"))
      .finally(() => setLoading(false));
  };

  useDidShow(loadOrders);

  const repeat = async (order) => {
    if (repeatingId) return;
    setRepeatingId(order.id);
    try {
      const draft = await repeatOrder(order.id, getCustomerId());
      const availableItems = draft.items
        .filter((item) => item.available)
        .map((item) => ({
          id: item.dish_id,
          name: item.name,
          description: item.description,
          category: item.category,
          price: item.price,
          image_url: item.image_url,
          quantity: item.quantity
        }));
      if (!availableItems.length) {
        Taro.showToast({ title: "这张点菜单里的菜暂时都不可点", icon: "none" });
        return;
      }
      replaceCart(availableItems);
      saveRepeatDraft({ source_order_id: draft.source_order_id, note: draft.note || "" });
      if (draft.unavailable_names?.length) {
        await Taro.showModal({
          title: "有些菜今天暂时没有",
          content: `${draft.unavailable_names.join("、")} 没有放进清单，其余菜已经复制好了。`,
          showCancel: false
        });
      }
      Taro.navigateTo({ url: "/pages/cart/index" });
    } catch (requestError) {
      Taro.showToast({ title: requestError.message || "再次点单失败", icon: "none" });
    } finally {
      setRepeatingId(null);
    }
  };

  if (loading) return <View className="page"><AsyncState message="正在找回之前点过的菜…" /></View>;
  if (error) {
    return (
      <View className="page">
        <AsyncState type="error" message={error} onRetry={loadOrders} />
      </View>
    );
  }

  return (
    <View className="page">
      <View className="my-orders-head">
        <View>
          <Text className="eyebrow">ORDER HISTORY</Text>
          <Text className="section-title">我的点菜单</Text>
        </View>
        <View className="secondary-button head-button" onClick={() => Taro.switchTab({ url: "/pages/menu/index" })}>
          <Text>去点菜</Text>
        </View>
      </View>

      {orders.length === 0 ? (
        <View className="empty-card card">
          <View className="empty-icon">🍜</View>
          <Text className="empty-title">还没有点过菜哦</Text>
          <Text className="empty-desc">快去选一道想吃的吧</Text>
          <View className="primary-button" onClick={() => Taro.switchTab({ url: "/pages/menu/index" })}>
            <Text>去看看菜单</Text>
          </View>
        </View>
      ) : (
        <View className="order-list">
          {orders.map((order) => (
            <View className="order-card card" key={order.id}>
              <View className="order-head">
                <View>
                  <Text className="order-title">订单 #{order.id}</Text>
                  <Text className="order-time">{formatTime(order.created_at)}</Text>
                </View>
                <Text className="status-pill">{order.status}</Text>
              </View>

              <Text className="friendly-status">{STATUS_TEXT[order.status] || order.status}</Text>

              <View className="dish-lines">
                {order.items.map((item) => (
                  <View className="dish-line" key={item.id}>
                    <Text>{item.dish_name}</Text>
                    <Text>× {item.quantity}</Text>
                  </View>
                ))}
              </View>

              {order.desired_time && (
                <View className="meta-line">
                  <Text>希望用餐</Text>
                  <Text>{order.desired_time}</Text>
                </View>
              )}
              {order.note && (
                <View className="meta-line">
                  <Text>备注</Text>
                  <Text>{order.note}</Text>
                </View>
              )}

              <View className="order-foot">
                <Text className={order.has_review ? "reviewed" : ""}>{reviewHint(order)}</Text>
                <View className="order-card-actions">
                  <View className="repeat-order-button" onClick={() => repeat(order)}>
                    <Text>{repeatingId === order.id ? "复制中…" : "♡ 再做一次"}</Text>
                  </View>
                  <View
                    className="small-button"
                    onClick={() => Taro.navigateTo({ url: `/pages/order-detail/index?id=${order.id}` })}
                  >
                    <Text>查看详情</Text>
                  </View>
                </View>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
