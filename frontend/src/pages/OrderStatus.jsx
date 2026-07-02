import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { createReview, getOrder } from "../api";

const STEPS = ["待接单", "已接单", "制作中", "已完成"];

export default function OrderStatus() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [rating, setRating] = useState(5);
  const [wantAgain, setWantAgain] = useState("想吃");
  const [comment, setComment] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    let active = true;
    const load = () =>
      getOrder(id)
        .then((data) => active && setOrder(data))
        .catch(() => active && setError("订单没有找到。"));
    load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [id]);

  if (error) return <div className="content state-box error">{error}</div>;
  if (!order) return <div className="content state-box">正在查询订单…</div>;

  const currentStep = STEPS.indexOf(order.status);
  const unavailable = order.status === "暂时做不了";

  const submitReview = async (event) => {
    event.preventDefault();
    setReviewing(true);
    setReviewError("");
    try {
      const review = await createReview(order.id, {
        rating,
        want_again: wantAgain,
        comment,
      });
      setOrder((current) => ({ ...current, review }));
    } catch (requestError) {
      setReviewError(requestError.response?.data?.detail || "评价提交失败，请稍后再试。");
    } finally {
      setReviewing(false);
    }
  };

  return (
    <section className="status-page">
      <div className="success-heart">♥</div>
      <h1>{unavailable ? "这次可能要换一道啦" : "已经收到你的点菜啦"}</h1>
      <p>订单 #{order.id} · 状态会每 5 秒自动更新</p>
      <div className={`status-panel ${unavailable ? "unavailable" : ""}`}>
        {unavailable ? (
          <div className="unavailable-message">暂时做不了，看看其他想吃的好吗？</div>
        ) : (
          <div className="timeline">
            {STEPS.map((step, index) => (
              <div className={index <= currentStep ? "done" : ""} key={step}>
                <span>{index < currentStep ? "✓" : index + 1}</span>
                <small>{step}</small>
              </div>
            ))}
          </div>
        )}
        <div className="status-order-items">
          {order.items.map((item) => (
            <p key={item.id}><span>{item.dish_name} × {item.quantity}</span></p>
          ))}
          {order.desired_time && <p><span>希望用餐</span><strong>{order.desired_time}</strong></p>}
          {order.note && <p><span>备注</span><strong>{order.note}</strong></p>}
        </div>
      </div>
      {order.status !== "已完成" && (
        <p className="rating-wait-hint">♡ 做好之后就可以评价啦</p>
      )}
      {order.status === "已完成" && (
        <div className="review-panel">
          {order.review ? (
            <div className="review-result">
              <span className="eyebrow">LOVE REVIEW</span>
              <h2>谢谢你的评价呀</h2>
              <div className="heart-result" aria-label={`${order.review.rating} 颗爱心`}>
                {"♥".repeat(order.review.rating)}
                <span>{"♥".repeat(5 - order.review.rating)}</span>
              </div>
              <p><strong>下次还想吃吗：</strong>{order.review.want_again}</p>
              {order.review.comment && <p><strong>你的建议：</strong>{order.review.comment}</p>}
            </div>
          ) : (
            <form className="review-form" onSubmit={submitReview}>
              <span className="eyebrow">LOVE REVIEW</span>
              <h2>这顿饭合心意吗？</h2>
              <label>
                好吃程度
                <div className="heart-picker" aria-label="选择好吃程度">
                  {[1, 2, 3, 4, 5].map((value) => (
                    <button
                      type="button"
                      key={value}
                      className={value <= rating ? "active" : ""}
                      onClick={() => setRating(value)}
                      aria-label={`${value} 颗爱心`}
                    >
                      ♥
                    </button>
                  ))}
                </div>
              </label>
              <label>
                下次还想吃吗
                <div className="want-options">
                  {["想吃", "一般", "暂时不想"].map((value) => (
                    <button
                      type="button"
                      key={value}
                      className={wantAgain === value ? "active" : ""}
                      onClick={() => setWantAgain(value)}
                    >
                      {value}
                    </button>
                  ))}
                </div>
              </label>
              <label>
                文字建议（可选）
                <textarea
                  rows="3"
                  maxLength="500"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="比如：下次想再辣一点～"
                />
              </label>
              {reviewError && <p className="form-error">{reviewError}</p>}
              <button className="primary-button" type="submit" disabled={reviewing}>
                {reviewing ? "正在提交…" : "提交爱心评价"}
              </button>
            </form>
          )}
        </div>
      )}
      <div className="status-page-actions">
        <Link to="/my-orders" className="secondary-button">我的点菜单</Link>
        <Link to="/" className="secondary-button">再看看菜单</Link>
      </div>
    </section>
  );
}
