import Taro from "@tarojs/taro";

const ADMIN_TOKEN_KEY = "gf_admin_token";
const ADMIN_EXPIRES_KEY = "gf_admin_token_expires_at";

export function getAdminToken() {
  try {
    const expiresAt = Taro.getStorageSync(ADMIN_EXPIRES_KEY);
    if (expiresAt && Date.parse(expiresAt) <= Date.now()) {
      clearAdminToken();
      return "";
    }
    return Taro.getStorageSync(ADMIN_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function saveAdminToken(token, expiresAt) {
  Taro.setStorageSync(ADMIN_TOKEN_KEY, token);
  if (expiresAt) Taro.setStorageSync(ADMIN_EXPIRES_KEY, expiresAt);
}

export function clearAdminToken() {
  try {
    Taro.removeStorageSync(ADMIN_TOKEN_KEY);
    Taro.removeStorageSync(ADMIN_EXPIRES_KEY);
  } catch (error) {
    console.warn("清除管理登录状态失败", error);
  }
}
