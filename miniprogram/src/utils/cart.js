import Taro from "@tarojs/taro";

const CART_KEY = "gf_menu_cart";

export function getCart() {
  return Taro.getStorageSync(CART_KEY) || [];
}

export function saveCart(cart) {
  Taro.setStorageSync(CART_KEY, cart);
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
  Taro.removeStorageSync(CART_KEY);
}
