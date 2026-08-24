import { useEffect, useRef, useState } from "react";
import Taro, { useDidHide, useDidShow, useLoad } from "@tarojs/taro";
import { Text, Textarea, View } from "@tarojs/components";

import { createReview, getOrder } from "../../api";
import { ROUTES } from "../../config/routes";
import { ensureInvitePassed } from "../../utils/invite";
import { ACTIVE_ORDER_STATUSES, formatTime, orderHeadline, ORDER_STEPS, STATUS_TEXT } from "../../utils/status";
import "./index.css";

export default function OrderDetail() {
  const [orderId, setOrderId] = useState("");
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [rating, setRating] = useState(5);
  const [wantAgain, setWantAgain] = useState("想吃");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const pageVisibleRef = useRef(true);
  const orderLoadingRef = useRef(false);

  const loadOrder = async (id, silent = false) => {
    // Visibility hooks, retry taps and polling may coincide; only one request owns the page state.
    if (!id || orderLoadingRef.current) return;
    orderLoadingRef.current = true;
    if (!silent) setError("");
    try {
      setOrder(await getOrder(id));
      setError("");
    } catch (err) {
      if (err?.statusCode === 401) {
        ensureInvitePassed();
        return;
      }
      if (silent) {
        console.info("订单自动刷新稍后重试", err?.statusCode || err?.message);
        return;
      }
      setError(err.message || "订单没有找到");
    } finally {
      orderLoadingRef.current = false;
    }
  };

  useLoad((params) => {
    if (!ensureInvitePassed()) return;
    setOrderId(params.id);
    loadOrder(params.id);
  });

  useDidHide(() => {
    pageVisibleRef.current = false;
  });

  useDidShow(() => {
    pageVisibleRef.current = true;
    if (orderId) loadOrder(orderId);
  });

  useEffect(() => {
    if (!orderId || ["已完成", "暂时做不了"].includes(order?.status)) return undefined;
    const timer = setInterval(() => {
      if (pageVisibleRef.current) loadOrder(orderId, true);
    }, 5000);
    return () => clearInterval(timer);
  }, [orderId, order?.status]);

  const submitReview = async () => {
    if (!order || submitting) return;
    setSubmitting(true);
    try {
      const review = await createReview(order.id, {
        rating,
        want_again: wantAgain,
        comment
      });
      setOrder({ ...order, review, has_review: true });
      Taro.showToast({ title: "评价已提交", icon: "success" });
    } catch (err) {
      Taro.showToast({ title: err.message || "评价提交失败", icon: "none" });
    } finally {
      setSubmitting(false);
    }
  };

  if (error) {
    return (
      <View className="page">
        <View className="state-box error">
          <Text>{error}</Text>
          <View className="retry-button" onClick={() => loadOrder(orderId)}><Text>重新加载</Text></View>
        </View>
      </View>
    );
  }
  if (!order) return <View className="page"><View className="state-box">正在查询订单…</View></View>;

  const unavailable = order.status === "暂时做不了";
  const waitingForCompletion = ACTIVE_ORDER_STATUSES.includes(order.status);
  const currentStep = ORDER_STEPS.indexOf(order.status);

  return (
    <View className="page order-page">
      <View className={`success-heart ${unavailable ? "is-unavailable" : ""}`}>{unavailable ? "↻" : "♥"}</View>
      <Text className="order-main-title">{orderHeadline(order.status)}</Text>
      <Text className="order-subtitle">
        订单 #{order.id} · {waitingForCompletion ? "状态会自动更新" : unavailable ? "这份点菜单已结束" : "这份点菜单已完成"}
      </Text>

      <View className="status-card card">
        {unavailable ? (
          <View className="unavailable">暂时做不了了，看看其他想吃的好吗？</View>
        ) : (
          <View className="timeline">
            {ORDER_STEPS.map((step, index) => (
              <View className={`timeline-step ${index <= currentStep ? "done" : ""}`} key={step}>
                <Text className="timeline-dot">{index < currentStep ? "✓" : index + 1}</Text>
                <Text>{step}</Text>
              </View>
            ))}
          </View>
        )}

        <Text className="friendly-status">{STATUS_TEXT[order.status] || order.status}</Text>

        <View className="order-items">
          {order.items.map((item) => (
            <View className="order-item" key={item.id}>
              <Text>{item.dish_name}</Text>
              <Text>× {item.quantity}</Text>
            </View>
          ))}
        </View>

        <View className="meta-line">
          <Text>点菜时间</Text>
          <Text>{formatTime(order.created_at)}</Text>
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
      </View>

      {waitingForCompletion && <Text className="wait-hint">♥ 做好之后就可以评价啦</Text>}

      {order.status === "已完成" && (
        <View className="review-card card">
          {order.review ? (
            <View>
              <Text className="eyebrow">LOVE REVIEW</Text>
              <Text className="review-title">谢谢你的评价呀</Text>
              <Text className="heart-result">
                {"♥".repeat(order.review.rating)}
                {"♡".repeat(5 - order.review.rating)}
              </Text>
              <Text className="review-line">下次还想吃吗：{order.review.want_again}</Text>
              {order.review.comment && <Text className="review-line">你的建议：{order.review.comment}</Text>}
            </View>
          ) : (
            <View>
              <Text className="eyebrow">LOVE REVIEW</Text>
              <Text className="review-title">这顿饭合心意吗？</Text>

              <Text className="form-label">好吃程度</Text>
              <View className="heart-picker">
                {[1, 2, 3, 4, 5].map((value) => (
                  <View
                    key={value}
                    className={value <= rating ? "active" : ""}
                    onClick={() => setRating(value)}
                  >
                    <Text>♥</Text>
                  </View>
                ))}
              </View>

              <Text className="form-label">下次还想吃吗</Text>
              <View className="want-options">
                {["想吃", "一般", "暂时不想"].map((value) => (
                  <View
                    key={value}
                    className={wantAgain === value ? "active" : ""}
                    onClick={() => setWantAgain(value)}
                  >
                    <Text>{value}</Text>
                  </View>
                ))}
              </View>

              <Text className="form-label">文字建议（可选）</Text>
              <Textarea
                className="textarea"
                value={comment}
                maxlength={500}
                placeholder="比如：下次想再辣一点"
                onInput={(event) => setComment(event.detail.value)}
              />

              <View className={`primary-button submit-review ${submitting ? "disabled" : ""}`} onClick={submitReview}>
                <Text>{submitting ? "正在提交…" : "提交爱心评价"}</Text>
              </View>
            </View>
          )}
        </View>
      )}

      <View className="bottom-actions">
        <View className="secondary-button" onClick={() => Taro.switchTab({ url: ROUTES.ORDERS })}>
          <Text>我的点菜单</Text>
        </View>
        <View className="secondary-button" onClick={() => Taro.switchTab({ url: ROUTES.MENU })}>
          <Text>再看看菜单</Text>
        </View>
      </View>
    </View>
  );
}
