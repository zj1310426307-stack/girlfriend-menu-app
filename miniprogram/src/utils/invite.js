import Taro from "@tarojs/taro";
import { hasCustomerSession } from "./customer";

const INVITE_PASSED_KEY = "gf_invite_passed";

// Read the invite state defensively so a damaged storage cache cannot blank the app.
export function hasInvitePassed() {
  try {
    return Taro.getStorageSync(INVITE_PASSED_KEY) === "yes";
  } catch (error) {
    console.warn("读取邀请码状态失败，将重新验证邀请码", error);
    return false;
  }
}

// Persist a successful invite check for later visits on the same device.
export function passInvite() {
  try {
    Taro.setStorageSync(INVITE_PASSED_KEY, "yes");
  } catch (error) {
    console.warn("保存邀请码状态失败，本次访问仍可继续", error);
  }
}

// Clear the invite state when a fresh verification is required.
export function clearInvite() {
  try {
    Taro.removeStorageSync(INVITE_PASSED_KEY);
  } catch (error) {
    console.warn("清除邀请码状态失败", error);
  }
}

// Redirect protected pages to the home-page invite gate.
export function ensureInvitePassed() {
  if (!hasInvitePassed() || !hasCustomerSession()) {
    Taro.reLaunch({ url: "/pages/index/index" }).catch((error) => {
      console.error("返回邀请码页失败", error);
    });
    return false;
  }
  return true;
}
