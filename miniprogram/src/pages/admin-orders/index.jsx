import { useCallback, useEffect, useMemo, useState } from "react";
import Taro, { useDidShow, usePullDownRefresh } from "@tarojs/taro";
import { Picker, Text, View } from "@tarojs/components";

import { getAdminOrders, updateAdminOrderStatus } from "../../api";
import { connectAdminOrders } from "../../api/adminSocket";
import AdminNav from "../../components/AdminNav";
import { clearAdminToken, getAdminToken } from "../../utils/admin";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const STATUSES = ["待接单", "已接单", "制作中", "已完成", "暂时做不了"];
const STATUS_CLASS_NAMES = {
  "待接单": "pending",
  "已接单": "accepted",
  "制作中": "cooking",
  "已完成": "completed",
  "暂时做不了": "unavailable",
};

function formatTime(value) {
  if (!value) return "—";
  return String(value).replace("T", " ").slice(0, 16);
}

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [liveStatus, setLiveStatus] = useState("connecting");
  const [updatingId, setUpdatingId] = useState(null);
  const token = getAdminToken();

  const leaveToLogin = useCallback(() => {
    clearAdminToken();
    Taro.redirectTo({ url: "/pages/admin-login/index" });
  }, []);

  const load = useCallback(async (silent = false) => {
    if (!token) {
      leaveToLogin();
      return;
    }
    if (!silent) setLoading(true);
    try {
      const data = await getAdminOrders(token);
      setOrders(data);
      setError("");
    } catch (requestError) {
      if (requestError.statusCode === 401) {
        leaveToLogin();
        return;
      }
      setError(requestError.message || "订单加载失败，请稍后重试");
    } finally {
      if (!silent) setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [leaveToLogin, token]);

  useEffect(() => {
    if (!ensureInvitePassed() || !token) {
      if (!token) leaveToLogin();
      return undefined;
    }
    load();
    const live = connectAdminOrders({ token, onEvent: () => load(true), onStatus: setLiveStatus });
    const timer = setInterval(() => load(true), 12000);
    return () => {
      live.close();
      clearInterval(timer);
    };
  }, [leaveToLogin, load, token]);

  useDidShow(() => token && load(true));
  usePullDownRefresh(() => load());

  const pendingCount = useMemo(
    () => orders.filter((order) => ["待接单", "已接单", "制作中"].includes(order.status)).length,
    [orders]
  );

  const changeStatus = async (order, status) => {
    if (!status || status === order.status || updatingId) return;
    setUpdatingId(order.id);
    try {
      const updated = await updateAdminOrderStatus(order.id, status, token);
      setOrders((current) => current.map((item) => item.id === order.id ? updated : item));
      Taro.showToast({ title: `已改为${status}`, icon: "success" });
    } catch (requestError) {
      if (requestError.statusCode === 401) return leaveToLogin();
      Taro.showToast({ title: requestError.message || "状态修改失败", icon: "none" });
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <View className="mini-admin-page">
      <AdminNav active="orders" />
      <View className="mini-admin-head">
        <View>
          <Text className="mini-admin-kicker">LIVE KITCHEN BOARD</Text>
          <Text className="mini-admin-title">她今天点了什么</Text>
          <Text className="mini-admin-subtitle">新订单会自动出现在这里，下拉也可以立即刷新。</Text>
        </View>
        <View className={`mini-live mini-live-${liveStatus}`}><Text>{liveStatus === "online" ? "实时在线" : "正在连接"}</Text></View>
      </View>

      <View className="mini-admin-summary">
        <View><Text>全部订单</Text><Text>{orders.length}</Text></View>
        <View><Text>正在安排</Text><Text>{pendingCount}</Text></View>
        <View><Text>已经完成</Text><Text>{orders.filter((order) => order.status === "已完成").length}</Text></View>
      </View>

      {loading && <View className="mini-admin-state"><Text>正在翻开她的点菜单…</Text></View>}
      {error && <View className="mini-admin-state error" onClick={() => load()}><Text>{error}</Text><Text>点这里重新加载</Text></View>}
      {!loading && !error && orders.length === 0 && <View className="mini-admin-state"><Text>她还没有点菜，先等等她的消息吧。</Text></View>}

      <View className="mini-order-list">
        {orders.map((order) => (
          <View className="mini-order-card" key={order.id}>
            <View className="mini-order-top">
              <View><Text>订单 #{order.id}</Text><Text>{formatTime(order.created_at)}</Text></View>
              <Text className={`mini-status mini-status-${STATUS_CLASS_NAMES[order.status] || "pending"}`}>
                {order.status}
              </Text>
            </View>
            <View className="mini-order-dishes">
              {order.items.map((item) => (
                <View key={item.id}><Text>{item.dish_name}</Text><Text>× {item.quantity}</Text></View>
              ))}
            </View>
            <View className="mini-order-meta">
              <View><Text>希望用餐</Text><Text>{order.desired_time || "没有指定时间"}</Text></View>
              <View><Text>她的备注</Text><Text>{order.note || "没有特别备注"}</Text></View>
              <View><Text>爱心评价</Text><Text>{order.has_review ? `${"♥".repeat(order.review?.rating || 0)} ${order.review?.comment || "已评价"}` : "还没有评价"}</Text></View>
            </View>
            <Picker
              mode="selector"
              range={STATUSES}
              value={Math.max(0, STATUSES.indexOf(order.status))}
              disabled={updatingId === order.id}
              onChange={(event) => changeStatus(order, STATUSES[Number(event.detail.value)])}
            >
              <View className="mini-status-picker"><Text>{updatingId === order.id ? "正在更新…" : `修改状态 · ${order.status}`}</Text><Text>⌄</Text></View>
            </Picker>
          </View>
        ))}
      </View>

      <View className="mini-admin-actions">
        <View onClick={() => load()}><Text>刷新订单</Text></View>
        <View onClick={() => Taro.redirectTo({ url: "/pages/admin-dashboard/index" })}><Text>返回总览</Text></View>
      </View>
    </View>
  );
}
