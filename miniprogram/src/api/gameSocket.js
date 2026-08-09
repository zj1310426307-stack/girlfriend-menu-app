import Taro from "@tarojs/taro";

const GAME_SOCKET_ORIGIN = "wss://girlfriend-menu-api.onrender.com";

/** Connects every real-time game through the shared V2.1 wire protocol. */
export function connectGameRoom({
  roomCode,
  gameType,
  playerId,
  playerName,
  inviteCode,
  onState,
  onError,
  onStatus
}) {
  let socket = null;
  let open = false;
  let closed = false;
  let heartbeat;
  const pendingMessages = [];
  const connection = Taro.connectSocket({
    url: `${GAME_SOCKET_ORIGIN}/ws/game/${encodeURIComponent(roomCode)}`,
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
          player_id: playerId,
          name: playerName,
          invite_code: inviteCode
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
        if (message.type === "state" && message.game === gameType) {
          onState?.({ room_code: message.room_code, ...(message.data || {}) });
        }
        if (message.type === "error") onError?.(message.message || "游戏操作失败");
      } catch {
        onError?.("收到的房间数据不正确");
      }
    });
    socket.onError(() => {
      onStatus?.("offline");
      onError?.("实时连接失败，请检查 socket 合法域名");
    });
    socket.onClose(() => {
      open = false;
      clearInterval(heartbeat);
      onStatus?.("offline");
    });
  };

  if (connection && typeof connection.then === "function") {
    connection.then(bindSocket).catch(() => {
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
