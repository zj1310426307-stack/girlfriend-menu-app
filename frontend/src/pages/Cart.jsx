import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useCart } from "../App";
import { createOrder, resolveImageUrl } from "../api";
import { getCustomerId } from "../utils/customer";

export default function Cart() {
  const { cart, setQuantity, clearCart } = useCart();
  const navigate = useNavigate();
  const [note, setNote] = useState("");
  const [desiredTime, setDesiredTime] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const order = await createOrder({
        items: cart.map((item) => ({ dish_id: item.id, quantity: item.quantity })),
        note,
        desired_time: desiredTime,
        customer_id: getCustomerId(),
      });
      clearCart();
      navigate(`/orders/${order.id}`);
    } catch {
      setError("提交失败了，请稍后再试。");
      setSubmitting(false);
    }
  };

  if (cart.length === 0) {
    return (
      <section className="empty-page">
        <div className="empty-icon">🥣</div>
        <h1>点菜清单还是空的</h1>
        <p>去挑几道今天想吃的吧。</p>
        <Link to="/" className="primary-button">看看菜单</Link>
      </section>
    );
  }

  return (
    <section className="content narrow">
      <h1 className="page-title">我的点菜清单</h1>
      <div className="cart-list">
        {cart.map((item) => (
          <div className="cart-item" key={item.id}>
            {item.image_url ? <img src={resolveImageUrl(item.image_url)} alt="" /> : <div className="cart-thumb">🍳</div>}
            <div className="cart-item-main">
              <strong>{item.name}</strong>
              <span>¥{item.price.toFixed(2)}</span>
            </div>
            <div className="stepper">
              <button type="button" onClick={() => setQuantity(item.id, item.quantity - 1)}>−</button>
              <span>{item.quantity}</span>
              <button type="button" onClick={() => setQuantity(item.id, item.quantity + 1)}>+</button>
            </div>
          </div>
        ))}
      </div>
      <div className="form-card">
        <label>
          希望用餐时间
          <input
            type="datetime-local"
            value={desiredTime}
            onChange={(e) => setDesiredTime(e.target.value)}
          />
        </label>
        <label>
          给厨房的悄悄话
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="比如：不要香菜，想吃辣一点～"
            rows="3"
          />
        </label>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="checkout-bar">
        <div><span>合计</span><strong>¥{total.toFixed(2)}</strong></div>
        <button className="primary-button" type="button" disabled={submitting} onClick={submit}>
          {submitting ? "正在提交…" : "确认下单"}
        </button>
      </div>
    </section>
  );
}
