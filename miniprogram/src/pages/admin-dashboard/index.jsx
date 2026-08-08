import { useCallback, useEffect, useState } from "react";
import Taro, { usePullDownRefresh } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getAdminOrders, getAdminStatsSummary, getDishes } from "../../api";
import AdminNav from "../../components/AdminNav";
import { clearAdminToken, getAdminToken } from "../../utils/admin";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const CARDS = [
  { key: "orders", icon: "单", title: "实时订单", desc: "看她点了什么，及时修改制作状态", url: "/pages/admin-orders/index" },
  { key: "dishes", icon: "菜", title: "菜品管理", desc: "新增、编辑、下架菜品和上传照片", url: "/pages/admin-dishes/index" },
  { key: "stats", icon: "榜", title: "点菜统计", desc: "查看最爱吃的菜、评分和最近记录", url: "/pages/admin-stats/index" }
];

export default function AdminDashboardPage() {
  const [data, setData] = useState({ orders: [], dishes: [], summary: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const token = getAdminToken();

  const leaveToLogin = useCallback(() => {
    clearAdminToken();
    Taro.reLaunch({ url: "/pages/admin-login/index" });
  }, []);

  const load = useCallback(async () => {
    if (!token) return leaveToLogin();
    setLoading(true);
    try {
      const [orders, dishes, summary] = await Promise.all([
        getAdminOrders(token),
        getDishes(),
        getAdminStatsSummary(token)
      ]);
      setData({ orders, dishes, summary });
      setError("");
    } catch (requestError) {
      if (requestError.statusCode === 401) return leaveToLogin();
      setError(requestError.message || "管理数据加载失败，请稍后重试");
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [leaveToLogin, token]);

  useEffect(() => {
    if (ensureInvitePassed() && token) load();
    else if (!token) leaveToLogin();
  }, [leaveToLogin, load, token]);

  usePullDownRefresh(load);

  const activeOrders = data.orders.filter((order) => ["待接单", "已接单", "制作中"].includes(order.status)).length;
  const reviewedOrders = data.orders.filter((order) => order.has_review).length;

  return (
    <View className="admin-dashboard-page">
      <AdminNav active="dashboard" />
      <View className="dashboard-hero">
        <Text className="dashboard-kicker">PRIVATE KITCHEN</Text>
        <Text className="dashboard-title">今天的小厨房</Text>
        <Text className="dashboard-desc">订单、菜单和喜欢，都在小程序里照顾好。</Text>
      </View>

      {error && <View className="dashboard-state error" onClick={load}><Text>{error}</Text><Text>点这里重试</Text></View>}
      {!error && (
        <View className="dashboard-numbers">
          <View><Text>{loading ? "—" : activeOrders}</Text><Text>正在安排</Text></View>
          <View><Text>{loading ? "—" : data.dishes.length}</Text><Text>在售菜品</Text></View>
          <View><Text>{loading ? "—" : reviewedOrders}</Text><Text>收到评价</Text></View>
        </View>
      )}

      <View className="dashboard-menu">
        {CARDS.map((card) => (
          <View className={`dashboard-card dashboard-card-${card.key}`} key={card.key} onClick={() => Taro.redirectTo({ url: card.url })}>
            <View className="dashboard-card-icon"><Text>{card.icon}</Text></View>
            <View className="dashboard-card-copy">
              <Text>{card.title}</Text>
              <Text>{card.desc}</Text>
            </View>
            <Text className="dashboard-card-arrow">›</Text>
          </View>
        ))}
      </View>

      <View className="dashboard-note">
        <Text>小程序专属管理端</Text>
        <Text>网页端取消后，所有日常操作都从这里完成。</Text>
      </View>
    </View>
  );
}
