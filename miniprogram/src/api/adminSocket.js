import Taro from "@tarojs/taro";

const ADMIN_SOCKET_URL = "wss://girlfriend-menu-api.onrender.com/ws/admin/orders";

export function connectAdminOrders({ token, onEvent, onStatus }) {
  let closed = false;
  let socket;
  let heartbeat;
  let reconnectTimer;

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
        if (message.type === "ready") onStatus?.("online");
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
      if (!closed) reconnectTimer = setTimeout(open, 3000);
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
