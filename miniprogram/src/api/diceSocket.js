import Taro from "@tarojs/taro";

const DICE_SOCKET_ORIGIN = "wss://girlfriend-menu-api.onrender.com";

export function connectDiceRoom({ roomCode, playerId, playerName, inviteCode, onState, onError, onStatus }) {
  let socket = null;
  let open = false;
  let closed = false;
  let heartbeat;
  const pendingMessages = [];
  const connection = Taro.connectSocket({
    url: `${DICE_SOCKET_ORIGIN}/ws/games/dice/${encodeURIComponent(roomCode)}`,
    timeout: 20000,
  });

  const sendNow = (message) => socket?.send({ data: JSON.stringify(message) });
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
        player_id: playerId,
        name: playerName,
        invite_code: inviteCode,
      });
      pendingMessages.splice(0).forEach(sendNow);
      heartbeat = setInterval(() => sendNow({ type: "ping" }), 25000);
    });

    socket.onMessage((event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "room_state") onState?.(message);
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
      if (open) sendNow(message);
      else pendingMessages.push(message);
    },
    close() {
      closed = true;
      clearInterval(heartbeat);
      socket?.close({ code: 1000, reason: "leave room" });
    },
  };
}
