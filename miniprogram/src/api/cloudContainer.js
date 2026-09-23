import Taro from "@tarojs/taro";

import {
  CLOUDBASE_ENV_ID,
  CLOUDBASE_SERVICE,
  USE_CLOUDBASE_PRIVATE_ACCESS,
  WEBSOCKET_ORIGIN
} from "../config/env";

let cloudInitialization = null;

/** Resolve the native CloudBase API exposed by the WeChat runtime. */
function getCloudApi() {
  return Taro.cloud || globalThis.wx?.cloud || null;
}

/** Initialize the configured CloudBase environment once for all private calls. */
export function ensureCloudContainerReady() {
  if (!USE_CLOUDBASE_PRIVATE_ACCESS) return Promise.resolve(null);
  if (cloudInitialization) return cloudInitialization;

  cloudInitialization = Promise.resolve().then(() => {
    const cloud = getCloudApi();
    if (!cloud?.init || !cloud?.callContainer || !cloud?.connectContainer) {
      throw new Error("当前微信版本不支持云托管连接，请升级微信后重试");
    }
    cloud.init({ env: CLOUDBASE_ENV_ID, traceUser: true });
    return cloud;
  }).catch((error) => {
    cloudInitialization = null;
    throw error;
  });
  return cloudInitialization;
}

/** Send one HTTP request over the Mini Program-to-CloudBase private link. */
export async function callCloudContainer({ path, header = {}, ...options }) {
  const cloud = await ensureCloudContainerReady();
  return cloud.callContainer({
    ...options,
    config: { env: CLOUDBASE_ENV_ID },
    path,
    header: {
      ...header,
      "X-WX-SERVICE": CLOUDBASE_SERVICE
    }
  });
}

/** Open one WebSocket through CloudBase, with a direct-socket fallback outside production. */
export function connectContainerSocket(path, options = {}) {
  if (!USE_CLOUDBASE_PRIVATE_ACCESS) {
    return Taro.connectSocket({
      ...options,
      url: `${WEBSOCKET_ORIGIN}${path}`
    });
  }
  return ensureCloudContainerReady().then(async (cloud) => {
    const result = await cloud.connectContainer({
      service: CLOUDBASE_SERVICE,
      path
    });
    return result?.socketTask || result;
  });
}

export { USE_CLOUDBASE_PRIVATE_ACCESS };
