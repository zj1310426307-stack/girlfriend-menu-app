import { useRef, useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Image, Input, Text, Textarea, View } from "@tarojs/components";

import { createOrder, resolveImageUrl } from "../../api";
import { clearCart, getCart, getRepeatDraft, setCartItemQuantity } from "../../utils/cart";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

export default function Cart() {
  const [cart, setCart] = useState([]);
  const [desiredTime, setDesiredTime] = useState("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const idempotencyKey = useRef(`order_${Date.now()}_${Math.random().toString(36).slice(2, 12)}`);

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    setCart(getCart());
    const repeatDraft = getRepeatDraft();
    if (repeatDraft?.note && !note) setNote(repeatDraft.note);
  });

  const total = cart.reduce((sum, item) => sum + Number(item.price) * item.quantity, 0);

  const updateQuantity = (id, quantity) => {
    setCart(setCartItemQuantity(id, quantity));
  };

  const submit = async () => {
    if (cart.length === 0 || submitting) return;
    setSubmitting(true);
    try {
      const order = await createOrder({
        items: cart.map((item) => ({ dish_id: item.id, quantity: item.quantity })),
        note,
        desired_time: desiredTime,
        idempotency_key: idempotencyKey.current,
        source_order_id: getRepeatDraft()?.source_order_id || null
      });
      clearCart();
      setCart([]);
      Taro.redirectTo({ url: `/pages/order-detail/index?id=${order.id}` });
    } catch (err) {
      Taro.showToast({ title: err.message || "提交失败", icon: "none" });
      setSubmitting(false);
    }
  };

  if (cart.length === 0) {
    return (
      <View className="page empty-page">
        <View className="empty-icon">🥣</View>
        <Text className="empty-title">点菜清单还是空的</Text>
        <Text className="empty-desc">去挑几道今天想吃的吧。</Text>
        <View className="primary-button" onClick={() => Taro.switchTab({ url: "/pages/menu/index" })}>
          <Text>看看菜单</Text>
        </View>
      </View>
    );
  }

  return (
    <View className="page cart-page">
      <Text className="section-title">我的点菜清单</Text>
      {getRepeatDraft()?.source_order_id && (
        <View className="repeat-draft-hint"><Text>已从订单 #{getRepeatDraft().source_order_id} 复制，可以继续增减菜品再提交。</Text></View>
      )}
      <View className="cart-list card">
        {cart.map((item) => (
          <View className="cart-item" key={item.id}>
            {item.image_url ? (
              <Image className="cart-image" src={resolveImageUrl(item.image_url)} mode="aspectFill" />
            ) : (
              <View className="cart-image cart-placeholder">🍲</View>
            )}
            <View className="cart-main">
              <Text className="cart-name">{item.name}</Text>
              <Text className="cart-price">¥{Number(item.price).toFixed(2)}</Text>
            </View>
            <View className="stepper">
              <View className="stepper-button" onClick={() => updateQuantity(item.id, item.quantity - 1)}>
                <Text>−</Text>
              </View>
              <Text>{item.quantity}</Text>
              <View className="stepper-button" onClick={() => updateQuantity(item.id, item.quantity + 1)}>
                <Text>+</Text>
              </View>
            </View>
          </View>
        ))}
      </View>

      <View className="form-card card">
        <Text className="form-label">希望用餐时间</Text>
        <Input
          className="input"
          value={desiredTime}
          placeholder="比如：今晚 7 点"
          onInput={(event) => setDesiredTime(event.detail.value)}
        />
        <Text className="form-label">给厨房的悄悄话</Text>
        <Textarea
          className="textarea"
          value={note}
          maxlength={500}
          placeholder="比如：不要香菜，想吃辣一点"
          onInput={(event) => setNote(event.detail.value)}
        />
      </View>

      <View className="checkout card">
        <View>
          <Text className="muted">合计</Text>
          <Text className="checkout-total">¥{total.toFixed(2)}</Text>
        </View>
        <View className={`primary-button checkout-button ${submitting ? "disabled" : ""}`} onClick={submit}>
          <Text>{submitting ? "正在提交…" : "确认下单"}</Text>
        </View>
      </View>
    </View>
  );
}
