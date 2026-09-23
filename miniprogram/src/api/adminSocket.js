import { connectContainerSocket } from "./cloudContainer";

const ADMIN_SOCKET_PATH = "/ws/admin/orders";
const RETRY_DELAYS = [1000, 2000, 4000, 8000, 15000, 30000];

/** Maintain the administrator event stream across CloudBase and network reconnects. */
export function connectAdminOrders({ token, onEvent, onStatus }) {
  let closed = false;
  let socket;
  let connecting = false;
  let heartbeat;
  let reconnectTimer;
  let retryIndex = 0;
  let connectionGeneration = 0;

  const scheduleReconnect = () => {
    if (closed) return;
    const base = RETRY_DELAYS[Math.min(retryIndex, RETRY_DELAYS.length - 1)];
    retryIndex += 1;
    const jitter = Math.round(base * (Math.random() * 0.3 - 0.15));
    reconnectTimer = setTimeout(open, Math.max(500, base + jitter));
  };

  const bindSocket = (socketTask, generation) => {
    connecting = false;
    if (closed || generation !== connectionGeneration) {
      socketTask?.close?.({ code: 1000, reason: "cancelled" });
      return;
    }
    socket = socketTask;
    if (!socket) {
      onStatus?.("offline");
      scheduleReconnect();
      return;
    }
    socket.onOpen(() => {
      if (closed || generation !== connectionGeneration) return;
      socket.send({ data: JSON.stringify({ type: "auth", token }) });
      clearInterval(heartbeat);
      heartbeat = setInterval(() => {
        socket?.send({ data: JSON.stringify({ type: "ping" }) });
      }, 20000);
    });
    socket.onMessage((event) => {
      if (closed || generation !== connectionGeneration) return;
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
      } catch {
        console.info("[network] ADMIN_SOCKET_MESSAGE_INVALID");
      }
    });
    socket.onError(() => {
      if (closed || generation !== connectionGeneration) return;
      onStatus?.("offline");
    });
    socket.onClose(() => {
      if (generation !== connectionGeneration) return;
      clearInterval(heartbeat);
      socket = null;
      onStatus?.("offline");
      scheduleReconnect();
    });
  };

  const open = () => {
    if (closed || connecting) return;
    connecting = true;
    const generation = ++connectionGeneration;
    onStatus?.("connecting");
    let connection;
    try {
      connection = connectContainerSocket(ADMIN_SOCKET_PATH);
    } catch {
      connecting = false;
      onStatus?.("offline");
      scheduleReconnect();
      return;
    }
    Promise.resolve(connection)
      .then((socketTask) => bindSocket(socketTask, generation))
      .catch(() => {
        if (closed || generation !== connectionGeneration) return;
        connecting = false;
        onStatus?.("offline");
        scheduleReconnect();
      });
  };

  open();
  return {
    close() {
      closed = true;
      connecting = false;
      connectionGeneration += 1;
      clearInterval(heartbeat);
      clearTimeout(reconnectTimer);
      socket?.close({ code: 1000, reason: "leave admin" });
    }
  };
}
