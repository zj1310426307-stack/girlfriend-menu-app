import Taro from "@tarojs/taro";

import { CART_STORAGE_KEY, REPEAT_DRAFT_STORAGE_KEY } from "./sessionOwnedStorage";

export function getCart() {
  return Taro.getStorageSync(CART_STORAGE_KEY) || [];
}

export function saveCart(cart) {
  Taro.setStorageSync(CART_STORAGE_KEY, cart);
}

export function replaceCart(cart) {
  saveCart(cart);
  return cart;
}

export function saveRepeatDraft(draft) {
  Taro.setStorageSync(REPEAT_DRAFT_STORAGE_KEY, draft);
}

export function getRepeatDraft() {
  return Taro.getStorageSync(REPEAT_DRAFT_STORAGE_KEY) || null;
}

export function addToCart(dish) {
  const cart = getCart();
  const found = cart.find((item) => item.id === dish.id);
  const nextCart = found
    ? cart.map((item) =>
        item.id === dish.id ? { ...item, quantity: item.quantity + 1 } : item
      )
    : [...cart, { ...dish, quantity: 1 }];
  saveCart(nextCart);
  return nextCart;
}

export function setCartItemQuantity(id, quantity) {
  const cart = getCart();
  const nextCart =
    quantity <= 0
      ? cart.filter((item) => item.id !== id)
      : cart.map((item) => (item.id === id ? { ...item, quantity } : item));
  saveCart(nextCart);
  return nextCart;
}

export function clearCart() {
  Taro.removeStorageSync(CART_STORAGE_KEY);
  Taro.removeStorageSync(REPEAT_DRAFT_STORAGE_KEY);
}
