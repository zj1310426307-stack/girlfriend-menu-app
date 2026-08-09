import Taro from "@tarojs/taro";
import { WEBSOCKET_ORIGIN } from "../config/env";

const ADMIN_SOCKET_URL = `${WEBSOCKET_ORIGIN}/ws/admin/orders`;
const RETRY_DELAYS = [1000, 2000, 4000, 8000, 15000, 30000];

export function connectAdminOrders({ token, onEvent, onStatus }) {
  let closed = false;
  let socket;
  let heartbeat;
  let reconnectTimer;
  let retryIndex = 0;

  const scheduleReconnect = () => {
    if (closed) return;
    const base = RETRY_DELAYS[Math.min(retryIndex, RETRY_DELAYS.length - 1)];
    retryIndex += 1;
    const jitter = Math.round(base * (Math.random() * 0.3 - 0.15));
    reconnectTimer = setTimeout(open, Math.max(500, base + jitter));
  };

  const open = () => {
    if (closed) return;
    onStatus?.("connecting");
    socket = Taro.connectSocket({ url: ADMIN_SOCKET_URL });
    socket.onOpen(() => {
      socket.send({ data: JSON.stringify({ type: "auth", token }) });
      clearInterval(heartbeat);
      heartbeat = setInterval(() => {
        socket?.send({ data: JSON.stringify({ type: "ping" }) });
      }, 20000);
    });
    socket.onMessage((event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "ready") {
          retryIndex = 0;
          onStatus?.("online");
          onEvent?.(message); // caller refetches to recover events missed while offline
        }
        if (["order_created", "order_status_changed", "order_reviewed"].includes(message.type)) {
          onEvent?.(message);
        }
      } catch (error) {
        console.warn("管理订单消息解析失败", error);
      }
    });
    socket.onError(() => onStatus?.("offline"));
    socket.onClose(() => {
      clearInterval(heartbeat);
      onStatus?.("offline");
      scheduleReconnect();
    });
  };

  open();
  return {
    close() {
      closed = true;
      clearInterval(heartbeat);
      clearTimeout(reconnectTimer);
      socket?.close({ code: 1000, reason: "leave admin" });
    }
  };
}
