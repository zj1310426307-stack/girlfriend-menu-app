import { useRef, useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getMyOrders, repeatOrder } from "../../api";
import AsyncState from "../../components/AsyncState";
import PageSyncNotice from "../../components/PageSyncNotice";
import { replaceCart, saveRepeatDraft } from "../../utils/cart";
import { getAuthenticatedCustomerId, getCustomerId, hasCustomerSession } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import {
  claimPageRefresh,
  PAGE_SNAPSHOT_MAX_AGE,
  readPageSnapshot,
  releasePageRefresh,
  writePageSnapshot
} from "../../utils/pageSnapshot";
import { formatTime, reviewHint, STATUS_TEXT } from "../../utils/status";
import "./index.css";

/** Restore a recent, structurally safe order list before the tab requests fresh data. */
function createInitialOrdersState() {
  if (!hasCustomerSession()) return { orders: [], hasSnapshot: false };
  const customerId = getAuthenticatedCustomerId();
  const snapshot = readPageSnapshot("orders", customerId, PAGE_SNAPSHOT_MAX_AGE.orders);
  const orders = Array.isArray(snapshot?.orders)
    && snapshot.orders.every((order) => Array.isArray(order?.items))
    ? snapshot.orders
    : [];
  return { orders, hasSnapshot: Boolean(snapshot && orders === snapshot.orders) };
}

/** Order history keeps the last verified list visible while refreshing in the background. */
export default function MyOrders() {
  const [initialOrders] = useState(createInitialOrdersState);
  const [orders, setOrders] = useState(initialOrders.orders);
  const [loading, setLoading] = useState(!initialOrders.hasSnapshot);
  const [hasLoaded, setHasLoaded] = useState(initialOrders.hasSnapshot);
  const [error, setError] = useState("");
  const [repeatingId, setRepeatingId] = useState(null);
  const ordersLoadingRef = useRef(false);

  /** Own one order-list read so repeated tab events cannot compete for state. */
  const loadOrders = async ({ force = false } = {}) => {
    if (!ensureInvitePassed()) return;
    if (ordersLoadingRef.current) return;
    const customerId = getCustomerId();
    if (!claimPageRefresh("orders", customerId, { force })) return;
    ordersLoadingRef.current = true;
    setLoading(true);
    setError("");
    try {
      const nextOrders = await getMyOrders(customerId);
      setOrders(nextOrders);
      setHasLoaded(true);
      writePageSnapshot("orders", customerId, { orders: nextOrders });
    } catch (requestError) {
      releasePageRefresh("orders", customerId);
      setError(requestError.message || "历史点菜单加载失败");
    } finally {
      setLoading(false);
      ordersLoadingRef.current = false;
    }
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

  if (loading && !hasLoaded) return <View className="page"><AsyncState message="正在找回之前点过的菜…" /></View>;
  if (error && !hasLoaded) {
    return (
      <View className="page">
        <AsyncState type="error" message={error} onRetry={() => loadOrders({ force: true })} />
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

      <PageSyncNotice loading={loading} offline={Boolean(error)} onRetry={() => loadOrders({ force: true })} />

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
