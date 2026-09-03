import Taro from "@tarojs/taro";
import { WEBSOCKET_ORIGIN } from "../config/env";
import { getCustomerToken } from "../utils/customer";

const HEARTBEAT_INTERVAL_MS = 25000;
const MAX_PENDING_MESSAGES = 20;
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30000;
const RECONNECT_JITTER_RATIO = 0.25;

function isHeartbeat(message) {
  const type = String(message?.type || "").toLowerCase();
  return type === "ping" || type === "pong" || type === "heartbeat";
}

function reconnectDelay(attempt) {
  const exponential = Math.min(
    RECONNECT_BASE_DELAY_MS * (2 ** Math.max(0, attempt)),
    RECONNECT_MAX_DELAY_MS
  );
  const jitter = exponential * RECONNECT_JITTER_RATIO * ((Math.random() * 2) - 1);
  return Math.max(0, Math.round(exponential + jitter));
}

/** Connects every real-time game through the shared V2.1 wire protocol. */
export function connectGameRoom({
  roomCode,
  gameType,
  playerId,
  playerName,
  inviteCode,
  onState,
  onEvent,
  onError,
  onStatus
}) {
  let socket = null;
  let open = false;
  let connecting = false;
  let closed = false;
  let heartbeatTimer = null;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  let reconnectErrorNotified = false;
  const pendingMessages = [];

  const toEnvelope = (message) => {
    if (message?.game && message?.data) return message;
    const { type, ...data } = message || {};
    return { type, game: gameType, data };
  };

  const clearHeartbeat = () => {
    if (heartbeatTimer !== null) clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  };

  const clearReconnect = () => {
    if (reconnectTimer !== null) clearTimeout(reconnectTimer);
    reconnectTimer = null;
  };

  const enqueue = (message) => {
    if (closed || isHeartbeat(message)) return;
    if (pendingMessages.length >= MAX_PENDING_MESSAGES) pendingMessages.shift();
    pendingMessages.push(message);
  };

  const sendNow = (message) => {
    if (!socket || !open || closed) return false;
    try {
      socket.send({ data: JSON.stringify(message) });
      return true;
    } catch {
      return false;
    }
  };

  const flushPending = () => {
    const queued = pendingMessages.splice(0);
    for (let index = 0; index < queued.length; index += 1) {
      if (sendNow(queued[index])) continue;
      queued.slice(index).forEach(enqueue);
      break;
    }
  };

  let startConnection;

  const notifyReconnectError = () => {
    if (reconnectErrorNotified || closed) return;
    reconnectErrorNotified = true;
    onError?.("实时连接失败，正在自动重连");
  };

  const scheduleReconnect = () => {
    if (closed || open || connecting || reconnectTimer !== null) return;
    const delay = reconnectDelay(reconnectAttempt);
    reconnectAttempt += 1;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      startConnection();
    }, delay);
  };

  const markDisconnected = (socketTask) => {
    if (socketTask !== socket) return;
    socket = null;
    open = false;
    connecting = false;
    clearHeartbeat();
    if (closed) return;
    onStatus?.("offline");
    scheduleReconnect();
  };

  const bindSocket = (socketTask) => {
    connecting = false;
    if (!socketTask) {
      scheduleReconnect();
      return;
    }
    if (closed) {
      socketTask.close?.({ code: 1000, reason: "cancelled" });
      return;
    }

    socket = socketTask;
    socketTask.onOpen(() => {
      if (closed || socketTask !== socket) return;
      open = true;
      connecting = false;
      reconnectAttempt = 0;
      reconnectErrorNotified = false;
      clearReconnect();
      clearHeartbeat();
      onStatus?.("online");
      sendNow({
        type: "join",
        game: gameType,
        data: {
          name: playerName,
          customer_token: getCustomerToken()
        }
      });
      flushPending();
      heartbeatTimer = setInterval(() => {
        sendNow({ type: "ping", game: gameType, data: {} });
      }, HEARTBEAT_INTERVAL_MS);
    });

    socketTask.onMessage((event) => {
      if (closed || socketTask !== socket) return;
      try {
        const message = JSON.parse(event.data);
        const messageType = String(message.type || "").toLowerCase();
        onEvent?.({ ...message, type: messageType });
        if (
          messageType === "state"
          && (!message.game || String(message.game).toLowerCase() === String(gameType).toLowerCase())
        ) {
          onState?.({ room_code: message.room_code, ...(message.data || {}) });
        }
        if (messageType === "error") {
          onError?.(message.message || message.data?.message || "游戏操作失败");
        }
      } catch {
        onError?.("收到的房间数据不正确");
      }
    });

    socketTask.onError(() => {
      if (closed || socketTask !== socket) return;
      markDisconnected(socketTask);
      notifyReconnectError();
    });

    socketTask.onClose(() => {
      markDisconnected(socketTask);
    });
  };

  startConnection = () => {
    if (closed || open || connecting) return;
    connecting = true;
    let connection;
    try {
      connection = Taro.connectSocket({
        url: `${WEBSOCKET_ORIGIN}/ws/game/${encodeURIComponent(roomCode)}`,
        timeout: 20000
      });
    } catch {
      connecting = false;
      onStatus?.("offline");
      notifyReconnectError();
      scheduleReconnect();
      return;
    }

    if (connection && typeof connection.then === "function") {
      connection.then(bindSocket).catch(() => {
        connecting = false;
        if (closed) return;
        onStatus?.("offline");
        notifyReconnectError();
        scheduleReconnect();
      });
    } else {
      bindSocket(connection);
    }
  };

  startConnection();

  return {
    send(message) {
      if (closed) return false;
      const envelope = toEnvelope(message);
      if (open && sendNow(envelope)) return true;
      enqueue(envelope);
      return false;
    },
    close() {
      if (closed) return;
      closed = true;
      open = false;
      connecting = false;
      clearHeartbeat();
      clearReconnect();
      pendingMessages.splice(0);
      const activeSocket = socket;
      socket = null;
      activeSocket?.close?.({ code: 1000, reason: "leave room" });
    }
  };
}

// Kept as an alias for callers that use the generic transport name.
export const createGameSocket = connectGameRoom;
