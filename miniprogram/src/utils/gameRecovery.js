import { issueReconnectToken, reconnectGame, sendPresence } from "../api";
import {
  readSessionGameReconnectToken,
  removeSessionGameReconnectToken,
  writeSessionGameReconnectToken
} from "./sessionOwnedStorage";

/** Reuse or issue one reconnect credential scoped to the authenticated customer. */
export async function ensureGameRecovery(customerId, roomCode) {
  const normalized = String(roomCode || "").trim().toUpperCase();
  if (!customerId || !normalized) return "";
  sendPresence(customerId).catch(() => {});
  const existing = readSessionGameReconnectToken(customerId, normalized);
  if (existing) return existing;
  try {
    const payload = await issueReconnectToken(customerId, normalized);
    writeSessionGameReconnectToken(customerId, normalized, payload.reconnect_token);
    return payload.reconnect_token;
  } catch (error) {
    console.warn("登记游戏恢复凭证失败，当前对局仍可继续", error);
    return "";
  }
}

/**
 * Restore a room only when the current device is already one of its members.
 *
 * Prefer the rotated reconnect credential because it survives a normal page
 * restart.  The authenticated state loader is the safe fallback for rooms
 * created before reconnect credentials were introduced.  Callers should keep
 * a 403 response in the lobby: it normally means the route is an invitation
 * for a new player rather than a resumable room.
 */
export async function recoverGameRoom(customerId, roomCode, loadState) {
  const normalized = String(roomCode || "").trim().toUpperCase();
  if (!customerId || !normalized || typeof loadState !== "function") return null;

  const storedToken = getGameReconnectToken(customerId, normalized);
  if (storedToken) {
    try {
      const recovered = await reconnectGame(storedToken);
      if (recovered?.state) {
        sendPresence(customerId).catch(() => {});
        return recovered.state;
      }
    } catch (error) {
      if ([401, 404].includes(error?.statusCode)) {
        removeSessionGameReconnectToken(customerId, normalized);
      }
    }
  }

  const payload = await loadState(normalized);
  ensureGameRecovery(customerId, normalized).catch(() => {});
  return payload;
}

/** Return only the reconnect credential owned by this customer and room pair. */
export function getGameReconnectToken(customerId, roomCode) {
  return readSessionGameReconnectToken(customerId, roomCode);
}
