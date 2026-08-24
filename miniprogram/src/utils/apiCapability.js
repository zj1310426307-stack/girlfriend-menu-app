import Taro from "@tarojs/taro";

const API_CAPABILITY_STORAGE_KEY = "gf_api_capability_cooldowns_v31";
const MAX_CAPABILITY_COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;
export const API_CAPABILITY_COOLDOWN_MS = 6 * 60 * 60 * 1000;

function capabilityKey(scope, capability) {
  return `${String(scope || "default")}:${String(capability || "unknown")}`;
}

function readCooldowns() {
  try {
    const value = Taro.getStorageSync(API_CAPABILITY_STORAGE_KEY);
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch (_) {
    return {};
  }
}

function writeCooldowns(cooldowns) {
  try {
    if (Object.keys(cooldowns).length) {
      Taro.setStorageSync(API_CAPABILITY_STORAGE_KEY, cooldowns);
    } else {
      Taro.removeStorageSync(API_CAPABILITY_STORAGE_KEY);
    }
  } catch (_) {
    // Capability caching is only an optimization; storage failures must fail open.
  }
}

/** Avoid repeatedly probing an optional endpoint that the current backend lacks. */
export function isApiCapabilityCoolingDown(scope, capability, now = Date.now()) {
  const cooldowns = readCooldowns();
  const key = capabilityKey(scope, capability);
  const until = Number(cooldowns[key]);
  if (
    Number.isFinite(until)
    && until > now
    && until - now <= MAX_CAPABILITY_COOLDOWN_MS
  ) return true;
  if (Object.prototype.hasOwnProperty.call(cooldowns, key)) {
    delete cooldowns[key];
    writeCooldowns(cooldowns);
  }
  return false;
}

/** Remember one compatibility miss without coupling production and staging. */
export function markApiCapabilityUnavailable(
  scope,
  capability,
  { now = Date.now(), duration = API_CAPABILITY_COOLDOWN_MS } = {}
) {
  const safeDuration = Math.min(
    Math.max(Number(duration) || API_CAPABILITY_COOLDOWN_MS, 1),
    MAX_CAPABILITY_COOLDOWN_MS
  );
  const cooldowns = readCooldowns();
  cooldowns[capabilityKey(scope, capability)] = now + safeDuration;
  writeCooldowns(cooldowns);
}

/** A successful probe immediately re-enables the optimized endpoint. */
export function clearApiCapabilityCooldown(scope, capability) {
  const cooldowns = readCooldowns();
  const key = capabilityKey(scope, capability);
  if (!Object.prototype.hasOwnProperty.call(cooldowns, key)) return;
  delete cooldowns[key];
  writeCooldowns(cooldowns);
}
