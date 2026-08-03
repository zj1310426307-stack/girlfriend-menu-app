import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getMyOrders } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { formatTime, reviewHint, STATUS_TEXT } from "../../utils/status";
import "./index.css";

export default function MyOrders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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

  if (loading) return <View className="page"><View className="state-box">正在找回之前点过的菜…</View></View>;
  if (error) {
    return (
      <View className="page">
        <View className="state-box error">
          <Text>{error}</Text>
          <View className="retry-button" onClick={loadOrders}><Text>重新加载</Text></View>
        </View>
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
        <View className="secondary-button head-button" onClick={() => Taro.reLaunch({ url: "/pages/index/index" })}>
          <Text>去点菜</Text>
        </View>
      </View>

      {orders.length === 0 ? (
        <View className="empty-card card">
          <View className="empty-icon">🍜</View>
          <Text className="empty-title">还没有点过菜哦</Text>
          <Text className="empty-desc">快去选一道想吃的吧</Text>
          <View className="primary-button" onClick={() => Taro.reLaunch({ url: "/pages/index/index" })}>
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
                <View
                  className="small-button"
                  onClick={() => Taro.navigateTo({ url: `/pages/order-detail/index?id=${order.id}` })}
                >
                  <Text>查看详情</Text>
                </View>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}
