import Taro from "@tarojs/taro";

const PAGE_SNAPSHOT_KEY = "gf_tab_snapshots_v31";
export const PAGE_SNAPSHOT_MAX_AGE = Object.freeze({
  menu: 24 * 60 * 60 * 1000,
  orders: 60 * 60 * 1000,
  games: 60 * 60 * 1000,
  couple: 6 * 60 * 60 * 1000
});
export const PAGE_REFRESH_MIN_INTERVAL = Object.freeze({
  menu: 2 * 60 * 1000,
  orders: 30 * 1000,
  games: 60 * 1000,
  couple: 2 * 60 * 1000
});
const pageRefreshStartedAt = new Map();

/** Read one recent tab snapshot only when it belongs to the authenticated customer. */
export function readPageSnapshot(scope, customerId, maxAge = PAGE_SNAPSHOT_MAX_AGE[scope]) {
  if (!scope || !customerId || !Number.isFinite(maxAge)) return null;
  try {
    const snapshots = Taro.getStorageSync(PAGE_SNAPSHOT_KEY) || {};
    const snapshot = snapshots[scope];
    const age = Date.now() - Number(snapshot?.savedAt);
    if (
      snapshot?.customerId !== customerId
      || !Number.isFinite(age)
      || age < 0
      || age > maxAge
      || snapshot?.payload === null
      || typeof snapshot?.payload !== "object"
    ) return null;
    return snapshot.payload;
  } catch (error) {
    console.info("页面快照读取失败，将使用在线数据", error?.message);
    return null;
  }
}

/** Store one tab's render payload without allowing storage errors to fail the request. */
export function writePageSnapshot(scope, customerId, payload) {
  if (!scope || !customerId || payload === null || typeof payload !== "object") return false;
  try {
    const snapshots = Taro.getStorageSync(PAGE_SNAPSHOT_KEY) || {};
    const ownedSnapshots = Object.fromEntries(
      Object.entries(snapshots).filter(([, snapshot]) => snapshot?.customerId === customerId)
    );
    Taro.setStorageSync(PAGE_SNAPSHOT_KEY, {
      ...ownedSnapshots,
      [scope]: { customerId, savedAt: Date.now(), payload }
    });
    return true;
  } catch (error) {
    console.info("页面快照保存失败，本次访问不受影响", error?.message);
    return false;
  }
}

/** Claim one bounded tab refresh while allowing explicit user retries to bypass cooldown. */
export function claimPageRefresh(scope, customerId, { force = false } = {}) {
  const minimumInterval = PAGE_REFRESH_MIN_INTERVAL[scope];
  if (!scope || !customerId || !Number.isFinite(minimumInterval)) return false;
  const key = `${customerId}:${scope}`;
  const now = Date.now();
  const previous = pageRefreshStartedAt.get(key) || 0;
  if (!force && now - previous < minimumInterval) return false;
  pageRefreshStartedAt.set(key, now);
  return true;
}

/** Release a failed refresh so the retry action can run immediately. */
export function releasePageRefresh(scope, customerId) {
  pageRefreshStartedAt.delete(`${customerId}:${scope}`);
}

/** Clear every private tab snapshot when the customer session is removed. */
export function clearPageSnapshots() {
  pageRefreshStartedAt.clear();
  try {
    Taro.removeStorageSync(PAGE_SNAPSHOT_KEY);
  } catch (error) {
    console.info("页面快照清理失败", error?.message);
  }
}
