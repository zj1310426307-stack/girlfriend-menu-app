const STATUS_OPTIONS = ["待接单", "已接单", "制作中", "已完成", "暂时做不了"];

export default function OrderCard({ order, onStatusChange }) {
  const total = order.items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  return (
    <article className="order-card">
      <div className="order-card-head">
        <div>
          <strong>订单 #{order.id}</strong>
          <p>{new Date(order.created_at).toLocaleString("zh-CN")}</p>
        </div>
        <span className={`status status-${order.status}`}>{order.status}</span>
      </div>
      <div className="order-items">
        {order.items.map((item) => (
          <div key={item.id}>
            <span>{item.dish_name} × {item.quantity}</span>
            <span>¥{(item.price * item.quantity).toFixed(2)}</span>
          </div>
        ))}
      </div>
      {order.desired_time && <p className="order-meta">🕐 希望用餐：{order.desired_time}</p>}
      {order.note && <p className="order-meta">💌 备注：{order.note}</p>}
      <p className={`review-badge ${order.review ? "reviewed" : ""}`}>
        {order.review ? `♥ 已评价 ${order.review.rating}/5` : "♡ 未评价"}
      </p>
      <div className="order-card-foot">
        <strong>合计 ¥{total.toFixed(2)}</strong>
        {onStatusChange && (
          <select value={order.status} onChange={(e) => onStatusChange(order.id, e.target.value)}>
            {STATUS_OPTIONS.map((status) => (
              <option key={status}>{status}</option>
            ))}
          </select>
        )}
      </div>
    </article>
  );
}
