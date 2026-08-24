import Taro from "@tarojs/taro";

import { clearHomeSnapshot } from "./homeSnapshot";
import { clearPageSnapshots } from "./pageSnapshot";
import { clearSessionOwnedStorage, removeStorageBestEffort } from "./sessionOwnedStorage";

const LEGACY_CUSTOMER_KEY = "gf_customer_id";
const CUSTOMER_ID_KEY = "gf_authenticated_customer_id";
const CUSTOMER_TOKEN_KEY = "gf_customer_token";
const CUSTOMER_EXPIRES_KEY = "gf_customer_expires_at";
const WECHAT_IDENTITY_BOUND_KEY = "gf_wechat_identity_bound";

/** Clear every render cache and local draft that belongs to one customer session. */
function clearCustomerOwnedState() {
  clearSessionOwnedStorage();
  clearHomeSnapshot();
  clearPageSnapshots();
}

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

/** Return only a verified-session owner without creating a legacy identity as a side effect. */
export function getAuthenticatedCustomerId() {
  return Taro.getStorageSync(CUSTOMER_ID_KEY) || "";
}

export function getCustomerToken() {
  return Taro.getStorageSync(CUSTOMER_TOKEN_KEY) || "";
}

export function hasCustomerSession() {
  const authenticated = Boolean(Taro.getStorageSync(CUSTOMER_ID_KEY) && getCustomerToken());
  if (!authenticated) return false;
  const expiresAt = Taro.getStorageSync(CUSTOMER_EXPIRES_KEY);
  if (!expiresAt) return true; // Compatibility with tokens saved before Phase 1.
  const expiresTime = Date.parse(expiresAt);
  if (Number.isFinite(expiresTime) && expiresTime <= Date.now()) {
    clearCustomerSession();
    return false;
  }
  return true;
}

/** Save a verified bearer and discard private state only when its owner changes. */
export function saveCustomerSession(session) {
  if (!session?.customer_id || !session?.customer_token) throw new Error("设备会话数据不完整");
  const previousCustomerId = getAuthenticatedCustomerId();
  if (previousCustomerId && previousCustomerId !== session.customer_id) {
    clearCustomerOwnedState();
    removeStorageBestEffort(WECHAT_IDENTITY_BOUND_KEY);
  }
  Taro.setStorageSync(CUSTOMER_ID_KEY, session.customer_id);
  Taro.setStorageSync(CUSTOMER_TOKEN_KEY, session.customer_token);
  if (session.expires_at) Taro.setStorageSync(CUSTOMER_EXPIRES_KEY, session.expires_at);
  else Taro.removeStorageSync(CUSTOMER_EXPIRES_KEY);
  return session.customer_id;
}

export function hasWeChatIdentityBinding() {
  return Boolean(Taro.getStorageSync(WECHAT_IDENTITY_BOUND_KEY));
}

export function markWeChatIdentityBound() {
  Taro.setStorageSync(WECHAT_IDENTITY_BOUND_KEY, "1");
}

/** Remove the authenticated session and every customer-owned local artifact best effort. */
export function clearCustomerSession() {
  // Deliberately preserve gf_customer_id so a failed/expired migration never destroys legacy ownership.
  clearCustomerOwnedState();
  removeStorageBestEffort(CUSTOMER_ID_KEY);
  removeStorageBestEffort(CUSTOMER_TOKEN_KEY);
  removeStorageBestEffort(CUSTOMER_EXPIRES_KEY);
  removeStorageBestEffort(WECHAT_IDENTITY_BOUND_KEY);
}
