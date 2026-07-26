import Taro from "@tarojs/taro";

const CUSTOMER_KEY = "gf_customer_id";

export function getCustomerId() {
  const existing = Taro.getStorageSync(CUSTOMER_KEY);
  if (existing) return existing;

  const random = Math.random().toString(36).slice(2, 10);
  const customerId = `gf_${Date.now()}_${random}`;
  Taro.setStorageSync(CUSTOMER_KEY, customerId);
  return customerId;
}
