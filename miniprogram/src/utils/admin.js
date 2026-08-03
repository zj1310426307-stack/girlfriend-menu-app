import Taro from "@tarojs/taro";

const ADMIN_TOKEN_KEY = "gf_admin_token";

export function getAdminToken() {
  try {
    return Taro.getStorageSync(ADMIN_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function saveAdminToken(token) {
  Taro.setStorageSync(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken() {
  try {
    Taro.removeStorageSync(ADMIN_TOKEN_KEY);
  } catch (error) {
    console.warn("清除管理登录状态失败", error);
  }
}
