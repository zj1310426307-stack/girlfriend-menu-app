import { useCallback, useEffect, useMemo, useState } from "react";
import Taro, { usePullDownRefresh } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import {
  getAdminDishStats,
  getAdminGameStats,
  getAdminOrders,
  getAdminRecentOrders,
  getAdminStatsSummary
} from "../../api";
import AdminNav from "../../components/AdminNav";
import { clearAdminToken, getAdminToken } from "../../utils/admin";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

function formatTime(value) {
  if (!value) return "还没有记录";
  return String(value).replace("T", " ").slice(0, 16);
}

export default function AdminStatsPage() {
  const [summary, setSummary] = useState(null);
  const [dishStats, setDishStats] = useState([]);
  const [recentOrders, setRecentOrders] = useState([]);
  const [orders, setOrders] = useState([]);
  const [gameStats, setGameStats] = useState(null);
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
      const [nextSummary, nextDishStats, nextRecent, nextOrders, nextGameStats] = await Promise.all([
        getAdminStatsSummary(token),
        getAdminDishStats(token),
        getAdminRecentOrders(token),
        getAdminOrders(token),
        getAdminGameStats(token).catch(() => null)
      ]);
      setSummary(nextSummary);
      setDishStats(nextDishStats);
      setRecentOrders(nextRecent);
      setOrders(nextOrders);
      setGameStats(nextGameStats);
      setError("");
    } catch (requestError) {
      if (requestError.statusCode === 401) return leaveToLogin();
      setError(requestError.message || "统计数据加载失败，请稍后重试");
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

  const reviews = useMemo(
    () => orders.filter((order) => order.review).map((order) => ({ order, review: order.review })),
    [orders]
  );

  const averageRating = useMemo(() => {
    if (!reviews.length) return "—";
    return (reviews.reduce((total, item) => total + item.review.rating, 0) / reviews.length).toFixed(1);
  }, [reviews]);

  const topRatedDish = useMemo(() => {
    const rated = new Map();
    reviews.forEach(({ order, review }) => {
      order.items.forEach((item) => {
        const current = rated.get(item.dish_name) || { total: 0, count: 0 };
        current.total += review.rating;
        current.count += 1;
        rated.set(item.dish_name, current);
      });
    });
    return [...rated.entries()]
      .map(([name, value]) => ({ name, average: value.total / value.count, count: value.count }))
      .sort((a, b) => b.average - a.average || b.count - a.count)[0] || null;
  }, [reviews]);

  const favoriteDish = dishStats[0];
  const latestDishNames = recentOrders[0]?.items?.map((item) => item.dish_name).join("、") || "还没有点过菜";

  return (
    <View className="admin-stats-page">
      <AdminNav active="stats" />
      <View className="stats-head">
        <Text className="stats-kicker">LOVE DATA</Text>
        <Text className="stats-title">她的口味小档案</Text>
        <Text className="stats-desc">每一张点菜单都算数，慢慢记住她最喜欢的味道。</Text>
      </View>

      {loading && <View className="stats-state"><Text>正在整理她的喜欢…</Text></View>}
      {error && <View className="stats-state error" onClick={load}><Text>{error}</Text><Text>点这里重试</Text></View>}

      {!loading && !error && (
        <>
          <View className="stats-summary-grid">
            <View><Text>{summary?.total_orders || 0}</Text><Text>总点菜次数</Text></View>
            <View><Text>{summary?.completed_orders || 0}</Text><Text>已完成订单</Text></View>
            <View><Text>{averageRating === "—" ? "—" : `${averageRating}♥`}</Text><Text>平均评分</Text></View>
            <View><Text>{reviews.length}</Text><Text>评价记录</Text></View>
          </View>

          <View className="stats-love-cards">
            <View className="stats-love-card favorite">
              <Text>最爱吃的菜</Text>
              <Text>{favoriteDish?.dish_name || "等她来点第一单"}</Text>
              <Text>{favoriteDish ? `累计点了 ${favoriteDish.total_quantity} 份` : "还没有统计数据"}</Text>
            </View>
            <View className="stats-love-card latest">
              <Text>最近想吃的菜</Text>
              <Text>{latestDishNames}</Text>
              <Text>{formatTime(recentOrders[0]?.created_at)}</Text>
            </View>
            <View className="stats-love-card rated">
              <Text>评分最高的菜</Text>
              <Text>{topRatedDish?.name || "等待第一条评价"}</Text>
              <Text>{topRatedDish ? `${topRatedDish.average.toFixed(1)} 颗爱心 · ${topRatedDish.count} 次评价` : "完成订单后就可以评价"}</Text>
            </View>
          </View>

          <View className="stats-section stats-game-section">
            <View className="stats-section-title"><Text>情侣游戏统计</Text><Text>V2.3 实时记录</Text></View>
            <View className="stats-game-grid">
              <View><Text>{gameStats?.total_games ?? gameStats?.total ?? 0}</Text><Text>总游戏次数</Text></View>
              <View><Text>{gameStats?.gomoku_games ?? gameStats?.gomoku?.total ?? 0}</Text><Text>五子棋对局</Text></View>
              <View><Text>{gameStats?.gomoku_win_rate != null ? `${Number(gameStats.gomoku_win_rate).toFixed(0)}%` : "—"}</Text><Text>五子棋胜率</Text></View>
              <View><Text>{gameStats?.love_score_change ?? gameStats?.score_change ?? 0}</Text><Text>游戏积分变化</Text></View>
            </View>
            <View className="stats-game-favorite"><Text>最常玩的游戏</Text><Text>{gameStats?.most_played_game?.name || gameStats?.most_played_game || "还没有游戏记录"}</Text></View>
          </View>

          <View className="stats-section">
            <View className="stats-section-title"><Text>最常点 Top 5</Text><Text>按份数统计</Text></View>
            {dishStats.length === 0 && <View className="stats-empty"><Text>还没有点菜记录</Text></View>}
            {dishStats.slice(0, 5).map((dish, index) => (
              <View className="stats-rank-row" key={`${dish.dish_id}-${dish.dish_name}`}>
                <Text>{index + 1}</Text>
                <View><Text>{dish.dish_name}</Text><Text>上次：{formatTime(dish.last_ordered_at)}</Text></View>
                <Text>{dish.total_quantity} 份</Text>
              </View>
            ))}
          </View>

          <View className="stats-section">
            <View className="stats-section-title"><Text>最近 10 次点菜</Text><Text>{formatTime(summary?.last_order_at)}</Text></View>
            {recentOrders.length === 0 && <View className="stats-empty"><Text>还没有点菜记录</Text></View>}
            {recentOrders.map((order) => (
              <View className="stats-order-row" key={order.id}>
                <View><Text>订单 #{order.id}</Text><Text>{formatTime(order.created_at)}</Text></View>
                <Text>{order.items.map((item) => `${item.dish_name}×${item.quantity}`).join("、")}</Text>
                <View><Text>{order.status}</Text><Text>{order.has_review ? "已评价" : "未评价"}</Text></View>
              </View>
            ))}
          </View>

          <View className="stats-section">
            <View className="stats-section-title"><Text>爱心评价记录</Text><Text>{reviews.length} 条</Text></View>
            {reviews.length === 0 && <View className="stats-empty"><Text>还没有收到评价</Text></View>}
            {reviews.slice(0, 20).map(({ order, review }) => (
              <View className="stats-review-row" key={review.id}>
                <View><Text>{"♥".repeat(review.rating)}{"♡".repeat(5 - review.rating)}</Text><Text>订单 #{order.id}</Text></View>
                <Text>{order.items.map((item) => item.dish_name).join("、")}</Text>
                <Text>{review.want_again} · {review.comment || "她没有写文字建议"}</Text>
                <Text>{formatTime(review.created_at)}</Text>
              </View>
            ))}
          </View>

          <View className="stats-section stats-all-dishes">
            <View className="stats-section-title"><Text>全部菜品点单次数</Text><Text>{dishStats.length} 道</Text></View>
            {dishStats.map((dish) => (
              <View key={`${dish.dish_id}-all`}><Text>{dish.dish_name}</Text><Text>{dish.total_quantity} 份</Text></View>
            ))}
          </View>
        </>
      )}
    </View>
  );
}
