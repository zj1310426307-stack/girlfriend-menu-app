import { useEffect, useMemo, useState } from "react";

import { getDishStats, getRecentStats, getStatsSummary } from "../api";

function formatTime(value) {
  return value ? new Date(value).toLocaleString("zh-CN") : "还没有点过";
}

export default function AdminStats() {
  const [summary, setSummary] = useState(null);
  const [dishStats, setDishStats] = useState([]);
  const [recentOrders, setRecentOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    Promise.all([
      getStatsSummary(),
      getDishStats(),
      getRecentStats(),
    ])
      .then(([summaryData, dishesData, recentData]) => {
        setSummary(summaryData);
        setDishStats(dishesData);
        setRecentOrders(recentData);
      })
      .catch((requestError) => {
        if (requestError.response?.status === 401) {
          localStorage.removeItem("admin_token");
          window.location.replace("/admin/login");
        } else {
          setError("统计数据加载失败，请检查后端。");
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const favoriteDish = dishStats[0];
  const recentDishNames = useMemo(
    () => recentOrders[0]?.items.map((item) => item.dish_name).join("、") || "还没有点菜",
    [recentOrders],
  );

  return (
    <section className="content admin-stats-page">
      <div className="stats-heading">
        <div>
          <span className="eyebrow">MENU MEMORIES</span>
          <h1>点菜历史统计</h1>
          <p>从每一次点菜里，慢慢记住她的偏爱。</p>
        </div>
      </div>

      {loading && <div className="state-box">正在整理点菜回忆…</div>}
      {error && <div className="state-box error">{error}</div>}

      {!loading && summary && (
        <>
          <div className="history-summary-grid">
            <article>
              <span>总点菜次数</span>
              <strong>{summary.total_orders}</strong>
              <small>其中 {summary.completed_orders} 单已完成</small>
            </article>
            <article>
              <span>最爱吃的菜</span>
              <strong>{favoriteDish?.dish_name || "等待第一单"}</strong>
              <small>{favoriteDish ? `累计点了 ${favoriteDish.total_quantity} 次` : "还没有统计数据"}</small>
            </article>
            <article>
              <span>最近想吃的菜</span>
              <strong>{recentDishNames}</strong>
              <small>{formatTime(summary.last_order_at)}</small>
            </article>
          </div>

          <div className="history-layout">
            <section className="history-card">
              <div className="section-title">
                <div><span className="eyebrow">TOP FIVE</span><h2>最常点的菜</h2></div>
              </div>
              {dishStats.slice(0, 5).map((dish, index) => (
                <div className="top-dish-row" key={`${dish.dish_id}-${dish.dish_name}`}>
                  <span className="rank">{index + 1}</span>
                  <div><strong>{dish.dish_name}</strong><small>最近：{formatTime(dish.last_ordered_at)}</small></div>
                  <b>{dish.total_quantity} 次</b>
                </div>
              ))}
              {dishStats.length === 0 && <p className="muted">还没有点菜记录。</p>}
            </section>

            <section className="history-card">
              <div className="section-title">
                <div><span className="eyebrow">ALL DISHES</span><h2>每道菜被点次数</h2></div>
              </div>
              <div className="dish-count-list">
                {dishStats.map((dish) => (
                  <div key={`all-${dish.dish_id}-${dish.dish_name}`}>
                    <span>{dish.dish_name}</span>
                    <strong>{dish.total_quantity}</strong>
                  </div>
                ))}
              </div>
              {dishStats.length === 0 && <p className="muted">还没有统计数据。</p>}
            </section>
          </div>

          <section className="history-card recent-history-card">
            <div className="section-title">
              <div><span className="eyebrow">RECENT TEN</span><h2>最近点菜记录</h2></div>
            </div>
            <div className="recent-history-list">
              {recentOrders.map((order) => (
                <article key={order.id}>
                  <div className="recent-order-head">
                    <strong>订单 #{order.id}</strong>
                    <span className={`status status-${order.status}`}>{order.status}</span>
                  </div>
                  <p>{order.items.map((item) => `${item.dish_name} × ${item.quantity}`).join("、")}</p>
                  <small>{formatTime(order.created_at)}</small>
                </article>
              ))}
            </div>
            {recentOrders.length === 0 && <p className="muted">最近还没有订单。</p>}
          </section>
        </>
      )}
    </section>
  );
}
