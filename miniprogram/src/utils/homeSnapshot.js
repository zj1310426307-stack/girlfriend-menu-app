import Taro from "@tarojs/taro";

const HOME_SNAPSHOT_KEY = "gf_home_snapshot_v31";
export const HOME_SNAPSHOT_MAX_AGE = 24 * 60 * 60 * 1000;

/** Confirm that a persisted snapshot still matches the home bootstrap contract. */
function isValidHomePayload(payload) {
  return Boolean(
    payload
    && Array.isArray(payload.dishes)
    && Array.isArray(payload.favorite_ranking)
    && Array.isArray(payload.today_tasks?.tasks)
    && Object.prototype.hasOwnProperty.call(payload, "recent_order")
    && (payload.recent_order === null || Array.isArray(payload.recent_order?.items))
  );
}

/** Read only the current customer's recent snapshot to prevent cross-account flashes. */
export function readHomeSnapshot(customerId, now = Date.now()) {
  if (!customerId) return null;
  try {
    const snapshot = Taro.getStorageSync(HOME_SNAPSHOT_KEY);
    const age = now - Number(snapshot?.savedAt);
    const invalid = (
      snapshot?.customerId !== customerId
      || !Number.isFinite(age)
      || age < 0
      || age > HOME_SNAPSHOT_MAX_AGE
      || !isValidHomePayload(snapshot?.payload)
    );
    if (invalid) {
      Taro.removeStorageSync(HOME_SNAPSHOT_KEY);
      return null;
    }
    return snapshot.payload;
  } catch (error) {
    console.info("首页快照读取失败，将使用在线数据", error?.message);
    return null;
  }
}

/** Persist one validated bootstrap response for immediate rendering on the next visit. */
export function writeHomeSnapshot(customerId, payload) {
  if (!customerId || !isValidHomePayload(payload)) return false;
  try {
    Taro.setStorageSync(HOME_SNAPSHOT_KEY, {
      customerId,
      savedAt: Date.now(),
      payload
    });
    return true;
  } catch (error) {
    console.info("首页快照保存失败，本次访问不受影响", error?.message);
    return false;
  }
}

/** Remove private summary data whenever the authenticated customer session is cleared. */
export function clearHomeSnapshot() {
  try {
    Taro.removeStorageSync(HOME_SNAPSHOT_KEY);
  } catch (error) {
    console.info("首页快照清理失败", error?.message);
  }
}
