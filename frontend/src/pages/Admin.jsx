import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  getApiErrorMessage,
  getOrders,
  subscribeToAdminOrderEvents,
  updateOrderStatus,
} from "../api";
import OrderCard from "../components/OrderCard";

export default function Admin() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [liveStatus, setLiveStatus] = useState("connecting");

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true);
    getOrders()
      .then((data) => {
        setOrders(data);
        setError("");
      })
      .catch((requestError) => {
        if (!silent) setError(getApiErrorMessage(requestError, "订单加载失败，请检查后端。"));
      })
      .finally(() => {
        if (!silent) setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") load(true);
    }, 10000);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(
    () => subscribeToAdminOrderEvents({
      onEvent: (message) => {
        if (["order_created", "order_status_changed", "order_reviewed"].includes(message.type)) {
          load(true);
        }
      },
      onStatus: setLiveStatus,
    }),
    [load],
  );

  const changeStatus = async (id, status) => {
    try {
      const updated = await updateOrderStatus(id, status);
      setOrders((list) => list.map((order) => (order.id === id ? updated : order)));
      setError("");
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, "订单状态修改失败，请重试。"));
    }
  };

  const stats = useMemo(() => {
    const reviewedOrders = orders.filter((order) => order.review);
    const average = reviewedOrders.length
      ? reviewedOrders.reduce((sum, order) => sum + order.review.rating, 0) / reviewedOrders.length
      : 0;
    const dishRatings = new Map();
    reviewedOrders.forEach((order) => {
      order.items.forEach((item) => {
        const current = dishRatings.get(item.dish_name) || { total: 0, count: 0 };
        current.total += order.review.rating;
        current.count += 1;
        dishRatings.set(item.dish_name, current);
      });
    });
    const highest = [...dishRatings.entries()]
      .map(([name, value]) => ({ name, score: value.total / value.count }))
      .sort((a, b) => b.score - a.score)[0];
    return { reviewedOrders, average, highest };
  }, [orders]);

  return (
    <section className="admin-page content">
      <div className="admin-heading">
        <div>
          <span className="eyebrow">KITCHEN BOARD</span>
          <h1>今天的订单</h1>
          <span className={`live-status live-${liveStatus}`}>
            <i />{liveStatus === "online" ? "实时接单中" : "正在连接实时订单"}
          </span>
        </div>
        <Link className="primary-button compact" to="/admin/dishes">管理菜品</Link>
      </div>
      {loading && <div className="state-box">正在查看订单…</div>}
      {error && <div className="state-box error">{error}</div>}
      {!loading && !error && orders.length === 0 && (
        <div className="state-box">还没有新订单，厨房可以先喝口水。</div>
      )}
      {!loading && !error && (
        <section className="review-stats">
          <div className="stat-card">
            <span>平均评分</span>
            <strong>{stats.average ? stats.average.toFixed(1) : "—"} <small>♥</small></strong>
          </div>
          <div className="stat-card">
            <span>评分最高的菜品</span>
            <strong>{stats.highest?.name || "等待评价"}</strong>
            {stats.highest && <small>{stats.highest.score.toFixed(1)} ♥</small>}
          </div>
          <div className="stat-card">
            <span>已评价订单</span>
            <strong>{stats.reviewedOrders.length}</strong>
          </div>
        </section>
      )}
      {stats.reviewedOrders.length > 0 && (
        <section className="review-records">
          <h2>评价记录</h2>
          {stats.reviewedOrders.map((order) => (
            <article key={order.review.id}>
              <div>
                <strong>订单 #{order.id}</strong>
                <span className="record-hearts">
                  {"♥".repeat(order.review.rating)}
                  <i>{"♥".repeat(5 - order.review.rating)}</i>
                </span>
              </div>
              <p>{order.items.map((item) => item.dish_name).join("、")}</p>
              <p>下次：{order.review.want_again}{order.review.comment ? ` · ${order.review.comment}` : ""}</p>
            </article>
          ))}
        </section>
      )}
      <div className="orders-grid">
        {orders.map((order) => (
          <OrderCard key={order.id} order={order} onStatusChange={changeStatus} />
        ))}
      </div>
    </section>
  );
}
