import Taro from "@tarojs/taro";

const LEGACY_CUSTOMER_KEY = "gf_customer_id";
const CUSTOMER_ID_KEY = "gf_authenticated_customer_id";
const CUSTOMER_TOKEN_KEY = "gf_customer_token";

export function getLegacyCustomerId() {
  const existing = Taro.getStorageSync(LEGACY_CUSTOMER_KEY);
  if (existing) return existing;
  const random = Math.random().toString(36).slice(2, 10);
  const legacyId = `gf_${Date.now()}_${random}`;
  Taro.setStorageSync(LEGACY_CUSTOMER_KEY, legacyId);
  return legacyId;
}

export function getCustomerId() {
  return Taro.getStorageSync(CUSTOMER_ID_KEY) || getLegacyCustomerId();
}

export function getCustomerToken() {
  return Taro.getStorageSync(CUSTOMER_TOKEN_KEY) || "";
}

export function hasCustomerSession() {
  return Boolean(Taro.getStorageSync(CUSTOMER_ID_KEY) && getCustomerToken());
}

export function saveCustomerSession(session) {
  if (!session?.customer_id || !session?.customer_token) throw new Error("设备会话数据不完整");
  Taro.setStorageSync(CUSTOMER_ID_KEY, session.customer_id);
  Taro.setStorageSync(CUSTOMER_TOKEN_KEY, session.customer_token);
  return session.customer_id;
}

export function clearCustomerSession() {
  // Deliberately preserve gf_customer_id so a failed/expired migration never destroys legacy ownership.
  Taro.removeStorageSync(CUSTOMER_ID_KEY);
  Taro.removeStorageSync(CUSTOMER_TOKEN_KEY);
}
