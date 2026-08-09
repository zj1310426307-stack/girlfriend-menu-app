import Taro from "@tarojs/taro";

import { issueReconnectToken, sendPresence } from "../api";

const tokenKey = (roomCode) => `gf_game_reconnect_${String(roomCode || "").toUpperCase()}`;

export async function ensureGameRecovery(customerId, roomCode) {
  const normalized = String(roomCode || "").trim().toUpperCase();
  if (!customerId || !normalized) return "";
  sendPresence(customerId).catch(() => {});
  const existing = Taro.getStorageSync(tokenKey(normalized));
  if (existing) return existing;
  try {
    const payload = await issueReconnectToken(customerId, normalized);
    Taro.setStorageSync(tokenKey(normalized), payload.reconnect_token);
    return payload.reconnect_token;
  } catch (error) {
    console.warn("登记游戏恢复凭证失败，当前对局仍可继续", error);
    return "";
  }
}

export function getGameReconnectToken(roomCode) {
  return Taro.getStorageSync(tokenKey(roomCode)) || "";
}
