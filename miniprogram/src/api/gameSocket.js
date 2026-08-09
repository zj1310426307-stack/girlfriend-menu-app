import Taro from "@tarojs/taro";
import { WEBSOCKET_ORIGIN } from "../config/env";
import { getCustomerToken } from "../utils/customer";


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
  let closed = false;
  let heartbeat;
  const pendingMessages = [];
  const connection = Taro.connectSocket({
    url: `${WEBSOCKET_ORIGIN}/ws/game/${encodeURIComponent(roomCode)}`,
    timeout: 20000
  });

  const sendNow = (message) => socket?.send({ data: JSON.stringify(message) });
  const toEnvelope = (message) => {
    if (message.game && message.data) return message;
    const { type, ...data } = message;
    return { type, game: gameType, data };
  };
  const bindSocket = (socketTask) => {
    if (closed) {
      socketTask.close({ code: 1000, reason: "cancelled" });
      return;
    }
    socket = socketTask;
    socket.onOpen(() => {
      open = true;
      onStatus?.("online");
      sendNow({
        type: "join",
        game: gameType,
        data: {
          name: playerName,
          customer_token: getCustomerToken()
        }
      });
      pendingMessages.splice(0).forEach(sendNow);
      heartbeat = setInterval(
        () => sendNow({ type: "ping", game: gameType, data: {} }),
        25000
      );
    });

    socket.onMessage((event) => {
      try {
        const message = JSON.parse(event.data);
        const messageType = String(message.type || "").toLowerCase();
        if (messageType === "session" && message.data?.room_session_token) {
          Taro.setStorageSync(`gf_room_session_${roomCode}`, message.data);
        }
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
    socket.onError(() => {
      if (closed) return;
      onStatus?.("offline");
      onError?.("实时连接失败，请检查 socket 合法域名");
    });
    socket.onClose(() => {
      open = false;
      clearInterval(heartbeat);
      if (!closed) onStatus?.("offline");
    });
  };

  if (connection && typeof connection.then === "function") {
    connection.then(bindSocket).catch(() => {
      if (closed) return;
      onStatus?.("offline");
      onError?.("实时连接失败，请检查网络");
    });
  } else {
    bindSocket(connection);
  }

  return {
    send(message) {
      const envelope = toEnvelope(message);
      if (open) sendNow(envelope);
      else pendingMessages.push(envelope);
    },
    close() {
      closed = true;
      clearInterval(heartbeat);
      socket?.close({ code: 1000, reason: "leave room" });
    }
  };
}
