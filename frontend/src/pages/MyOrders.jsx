import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getMyOrders } from "../api";
import { getCustomerId } from "../utils/customer";

const STATUS_TEXT = {
  待接单: "我还没看到，稍等一下",
  已接单: "收到，马上安排",
  制作中: "正在为你准备",
  已完成: "可以开吃啦",
  暂时做不了: "这道菜今天可能安排不了",
};

function reviewText(order) {
  if (order.has_review) return "♥ 已评价";
  if (order.status === "已完成") return "♡ 可以评价啦";
  return "♡ 做好后可评价";
}

export default function MyOrders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getMyOrders(getCustomerId())
      .then(setOrders)
      .catch(() => setError("点菜单暂时没有找到，请稍后再试。"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="content my-orders-page">
      <div className="my-orders-heading">
        <div>
          <span className="eyebrow">MY LITTLE ORDERS</span>
          <h1>我的点菜单</h1>
          <p>之前想吃的，都替你认真记在这里。</p>
        </div>
        <Link to="/" className="secondary-button">继续点菜</Link>
      </div>

      {loading && <div className="state-box">正在翻找以前的点菜单…</div>}
      {error && <div className="state-box error">{error}</div>}

      {!loading && !error && orders.length === 0 && (
        <div className="my-orders-empty">
          <div>🥣</div>
          <h2>还没有点过菜哦</h2>
          <p>快去选一道想吃的吧</p>
          <Link to="/" className="primary-button">去看看菜单</Link>
        </div>
      )}

      <div className="my-order-list">
        {orders.map((order) => (
          <article className="my-order-card" key={order.id}>
            <div className="my-order-head">
              <div>
                <strong>订单 #{order.id}</strong>
                <time>{new Date(order.created_at).toLocaleString("zh-CN")}</time>
              </div>
              <span className={`status status-${order.status}`}>{order.status}</span>
            </div>

            <p className="friendly-status">{STATUS_TEXT[order.status]}</p>

            <div className="my-order-dishes">
              {order.items.map((item) => (
                <div key={item.id}>
                  <span>{item.dish_name}</span>
                  <strong>× {item.quantity}</strong>
                </div>
              ))}
            </div>

            <div className="my-order-details">
              {order.desired_time && <p><span>希望用餐</span>{order.desired_time}</p>}
              {order.note && <p><span>备注</span>{order.note}</p>}
            </div>

            <div className="my-order-foot">
              <span className={order.has_review ? "reviewed" : ""}>{reviewText(order)}</span>
              <Link to={`/orders/${order.id}`}>查看详情 →</Link>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
