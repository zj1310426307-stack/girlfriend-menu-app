import Taro from "@tarojs/taro";

import { API_BASE_URL, API_ORIGIN } from "../config/env";
import { clearCustomerSession, getCustomerToken } from "../utils/customer";

const REQUEST_TIMEOUT = 45000;
const MAX_GET_RETRIES = 2;
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const normalizePath = (path) => (path.startsWith("/") ? path : `/${path}`);

/** Send one authenticated API request through the only HTTP transport boundary. */
export async function request(path, options = {}, attempt = 0) {
  const method = options.method || "GET";
  try {
    const response = await Taro.request({
      url: `${API_BASE_URL}${normalizePath(path)}`,
      method,
      timeout: options.timeout || REQUEST_TIMEOUT,
      data: options.data,
      header: {
        accept: "application/json",
        "content-type": "application/json",
        ...(getCustomerToken() ? { Authorization: `Bearer ${getCustomerToken()}` } : {}),
        ...(options.header || {})
      }
    });
    if (response.statusCode >= 200 && response.statusCode < 300) return response.data;
    if (
      method === "GET"
      && RETRYABLE_STATUS.has(response.statusCode)
      && attempt < MAX_GET_RETRIES
    ) {
      await wait((attempt + 1) * 700);
      return request(path, options, attempt + 1);
    }
    const detail = response.data?.detail || "请求失败，请稍后再试";
    const message = typeof detail === "string" ? detail : detail?.message || "请求参数不正确";
    const error = new Error(message);
    error.statusCode = response.statusCode;
    if (
      response.statusCode === 401
      && !options.preserveSession
      && !options.header?.Authorization
      && getCustomerToken()
    ) {
      clearCustomerSession();
    }
    if (detail?.current_version) error.currentVersion = detail.current_version;
    throw error;
  } catch (error) {
    if (method === "GET" && !error?.statusCode && attempt < MAX_GET_RETRIES) {
      await wait((attempt + 1) * 700);
      return request(path, options, attempt + 1);
    }
    if (!error?.statusCode && /timeout/i.test(error?.errMsg || error?.message || "")) {
      throw new Error("服务器正在醒来，请稍后重试");
    }
    if (
      !error?.statusCode
      && (!error?.message || /request:fail|network/i.test(error?.errMsg || error?.message || ""))
    ) {
      throw new Error("网络连接不稳定，请检查网络后重试");
    }
    throw error;
  }
}

/** Resolve stored relative image paths against the configured API origin. */
export function resolveImageUrl(imageUrl) {
  if (!imageUrl) return "";
  if (/^(https?:|data:|blob:)/i.test(imageUrl)) return imageUrl;
  return `${API_ORIGIN}${imageUrl.startsWith("/") ? imageUrl : `/${imageUrl}`}`;
}
