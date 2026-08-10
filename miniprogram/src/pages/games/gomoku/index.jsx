import { useEffect, useMemo, useRef, useState } from "react";
import Taro, { useRouter, useShareAppMessage } from "@tarojs/taro";
import { Button, Input, Text, View } from "@tarojs/components";

import { createGameRoom } from "../../../api";
import { connectGomokuRoom } from "../../../api/gomokuSocket";
import GomokuBoard from "../../../components/GomokuBoard";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery } from "../../../utils/gameRecovery";
import "./index.css";

const ROOM_CODE_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;
const EMPTY_BOARD = Array.from({ length: 15 }, () => Array(15).fill(0));
const EMPTY_ROOM = {
  phase: "waiting",
  players: [],
  board: EMPTY_BOARD,
  turn_id: null,
  winner_id: null,
  last_move: null,
  outcome: null,
  round: 1
};
const COUPLE_REWARDS = [
  "赢家决定下一顿吃什么",
  "输家负责一个温暖的拥抱",
  "赢家获得一次点菜优先权",
  "输家承包今天的一次洗碗",
  "一起拍张合照，记录这局胜负"
];

const playerIdOf = (player) => player?.id || player?.player_id;
const playerColor = (player, index) => {
  const raw = player?.color || player?.piece || player?.stone;
  if (raw === 1 || String(raw).toLowerCase() === "black") return "black";
  if (raw === 2 || String(raw).toLowerCase() === "white") return "white";
  return Number(player?.seat || index + 1) === 1 ? "black" : "white";
};
const colorName = (color) => color === "black" ? "黑棋" : "白棋";

function mergeIncrementalState(previous, message) {
  const data = message.data || message;
  if (message.type === "board_update" && !data.board && Number.isInteger(data.x) && Number.isInteger(data.y)) {
    const board = (previous.board || EMPTY_BOARD).map((row) => [...row]);
    board[data.y][data.x] = data.stone || data.color || data.player || 0;
    return { ...previous, ...data, board, last_move: { x: data.x, y: data.y } };
  }
  if (message.type === "game_over") {
    return { ...previous, ...data, phase: "finished", outcome: data.outcome || data };
  }
  return previous;
}

export default function GomokuPage() {
  const router = useRouter();
  const playerIdRef = useRef(getCustomerId());
  const socketRef = useRef(null);
  const authoritativeRoomRef = useRef(EMPTY_ROOM);
  const [allowed, setAllowed] = useState(false);
  const [playerName, setPlayerName] = useState("我");
  const [mode, setMode] = useState("couple");
  const [difficulty, setDifficulty] = useState("rule");
  const [joinCode, setJoinCode] = useState("");
  const [activeRoomCode, setActiveRoomCode] = useState("");
  const [room, setRoom] = useState(EMPTY_ROOM);
  const [connectionStatus, setConnectionStatus] = useState("offline");
  const [creating, setCreating] = useState(false);
  const [moving, setMoving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (activeRoomCode && connectionStatus === "online") ensureGameRecovery(playerIdRef.current, activeRoomCode);
  }, [activeRoomCode, connectionStatus]);

  const players = Array.isArray(room.players) ? room.players : [];
  const meIndex = players.findIndex((player) => playerIdOf(player) === playerIdRef.current);
  const me = players[meIndex];
  const opponent = players.find((player) => playerIdOf(player) !== playerIdRef.current);
  const myColor = me ? playerColor(me, meIndex) : "black";
  const winnerId = room.winner_id || room.outcome?.winner_id || room.outcome?.winner;
  const winner = players.find((player) => playerIdOf(player) === winnerId);
  const isFinished = room.phase === "finished" || room.status === "finished" || Boolean(winnerId) || room.is_draw || room.outcome?.is_draw || room.outcome?.draw;
  const isPlaying = ["playing", "active", "placing"].includes(String(room.phase || room.status).toLowerCase());
  const isMyTurn = isPlaying && room.turn_id === playerIdRef.current;
  const canMove = connectionStatus === "online" && isMyTurn && !moving && !isFinished;
  const showReady = players.length === 2 && (room.phase === "ready" || room.requires_ready);
  const isDraw = Boolean(room.is_draw || room.draw || room.outcome?.is_draw || room.outcome?.draw);

  const rewardText = useMemo(() => {
    const seed = `${activeRoomCode}${room.round || 1}`.split("").reduce((total, char) => total + char.charCodeAt(0), 0);
    return room.outcome?.reward || COUPLE_REWARDS[seed % COUPLE_REWARDS.length];
  }, [activeRoomCode, room.outcome?.reward, room.round]);

  const statusText = useMemo(() => {
    if (connectionStatus === "connecting") return "正在连接两个人的棋桌…";
    if (connectionStatus !== "online") return "连接已断开，棋盘暂时只读";
    if (players.length < 2) return "等待另一位玩家加入房间";
    if (showReady) return me?.ready ? "你已准备，等待对方" : "双方准备后开始对局";
    if (isFinished) {
      if (isDraw) return "这局和棋，默契不分高下";
      return winnerId === playerIdRef.current ? "五子连珠，你赢啦 ♥" : `${winner?.name || opponent?.name || "对方"} 赢了这局`;
    }
    if (isMyTurn) return `轮到你落${colorName(myColor)}`;
    return `等待 ${opponent?.name || "对方"} 落子`;
  }, [connectionStatus, isDraw, isFinished, isMyTurn, me, myColor, opponent, players.length, showReady, winner, winnerId]);

  const closeSocket = () => {
    socketRef.current?.close?.();
    socketRef.current = null;
  };

  const connectToRoom = (rawCode, { preserveBoard = false, nameOverride = "" } = {}) => {
    const normalized = String(rawCode || "").trim().toUpperCase();
    if (!ROOM_CODE_PATTERN.test(normalized)) {
      Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
      return;
    }
    closeSocket();
    setActiveRoomCode(normalized);
    setJoinCode(normalized);
    if (!preserveBoard) setRoom(EMPTY_ROOM);
    setErrorMessage("");
    setConnectionStatus("connecting");
    socketRef.current = connectGomokuRoom({
      roomCode: normalized,
      playerId: playerIdRef.current,
      playerName: nameOverride.trim() || playerName.trim() || "玩家",
      inviteCode: "",
      onState: (nextState) => {
        setRoom((previous) => {
          const merged = { ...previous, ...nextState, board: nextState.board || previous.board || EMPTY_BOARD };
          authoritativeRoomRef.current = merged;
          return merged;
        });
        setMoving(false);
        setErrorMessage("");
      },
      onEvent: (message) => {
        if (message.type === "board_update" || message.type === "game_over") {
          setRoom((previous) => mergeIncrementalState(previous, message));
          setMoving(false);
        }
      },
      onStatus: setConnectionStatus,
      onError: (message) => {
        setMoving(false);
        setRoom(authoritativeRoomRef.current);
        setErrorMessage(message);
        Taro.showToast({ title: message, icon: "none" });
      }
    });
  };

  useEffect(() => {
    const passed = ensureInvitePassed();
    setAllowed(passed);
    if (passed && router.params?.room) {
      const requestedName = router.params?.name ? decodeURIComponent(router.params.name) : "我";
      setPlayerName(requestedName);
      setTimeout(() => connectToRoom(router.params.room, { nameOverride: requestedName }), 0);
    }
    return closeSocket;
    // Room query is only consumed on first page mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useShareAppMessage(() => ({
    title: `来和我下一局五子棋，房间 ${activeRoomCode}`,
    path: `/pages/games/gomoku/index?room=${activeRoomCode}&name=${encodeURIComponent("女朋友")}`
  }));

  const makeRoom = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const result = await createGameRoom(
        "gomoku", playerIdRef.current, "", mode, difficulty
      );
      connectToRoom(result.room_code);
    } catch (error) {
      Taro.showToast({ title: error.message || "创建房间失败", icon: "none" });
    } finally {
      setCreating(false);
    }
  };

  const submitMove = (x, y) => {
    if (!canMove) {
      if (!isMyTurn) Taro.showToast({ title: "还没轮到你落子", icon: "none" });
      return;
    }
    setMoving(true);
    setRoom((previous) => {
      const board = (previous.board || EMPTY_BOARD).map((row) => [...row]);
      board[y][x] = myColor === "black" ? 1 : 2;
      return {
        ...previous,
        board,
        last_move: { x, y, player_id: playerIdRef.current, color: myColor, optimistic: true }
      };
    });
    Taro.vibrateShort({ type: "light" }).catch(() => {});
    socketRef.current?.send({ type: "move", x, y });
    setTimeout(() => setMoving(false), 3000);
  };

  const leaveRoom = () => {
    closeSocket();
    setActiveRoomCode("");
    setRoom(EMPTY_ROOM);
    setConnectionStatus("offline");
    setErrorMessage("");
  };

  const returnToGameCenter = () => {
    closeSocket();
    Taro.switchTab({ url: "/pages/games/index" });
  };

  if (!allowed) return <View className="gomoku-loading"><Text>正在返回邀请码页面…</Text></View>;

  if (!activeRoomCode) {
    return (
      <View className="gomoku-page gomoku-lobby">
        <View className="gomoku-lobby-hero">
          <Text className="gomoku-kicker">FIVE IN A ROW</Text>
          <Text className="gomoku-title">认真下一局</Text>
          <Text>15×15 实时棋盘。既可以邀请她，也可以先和 AI 热身。</Text>
          <View className="gomoku-preview"><Text>●</Text><Text>○</Text><Text>●</Text><Text>○</Text><Text>●</Text></View>
        </View>
        <View className="gomoku-lobby-card">
          <Text className="gomoku-label">我在房间里的名字</Text>
          <View className="gomoku-name-options">
            {["我", "女朋友"].map((name) => (
              <View key={name} className={playerName === name ? "active" : ""} onClick={() => setPlayerName(name)}><Text>{name}</Text></View>
            ))}
          </View>
          <Text className="gomoku-label">游戏模式</Text>
          <View className="gomoku-mode-options"><View className={mode === "couple" ? "active" : ""} onClick={() => setMode("couple")}><Text>情侣双人</Text><Text>实时房间</Text></View><View className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}><Text>人机练习</Text><Text>立即开局</Text></View></View>
          {mode === "ai" && <View className="gomoku-difficulty"><Text className={difficulty === "random" ? "active" : ""} onClick={() => setDifficulty("random")}>轻松 AI</Text><Text className={difficulty === "rule" ? "active" : ""} onClick={() => setDifficulty("rule")}>聪明 AI</Text><Text className={difficulty === "strategy" ? "active" : ""} onClick={() => setDifficulty("strategy")}>挑战 AI</Text></View>}
          <View className={`gomoku-primary ${creating ? "disabled" : ""}`} onClick={makeRoom}><Text>{creating ? "正在布置棋盘…" : mode === "ai" ? "开始人机对战" : "创建双人棋局"}</Text></View>
          <Text className="gomoku-or">或者加入她创建的房间</Text>
          <Input
            className="gomoku-input"
            value={joinCode}
            maxlength={6}
            placeholder="输入 6 位房间码"
            onInput={(event) => setJoinCode(event.detail.value.toUpperCase())}
            onConfirm={() => connectToRoom(joinCode)}
          />
          <View className="gomoku-secondary" onClick={() => connectToRoom(joinCode)}><Text>加入房间</Text></View>
        </View>
      </View>
    );
  }

  return (
    <View className="gomoku-page gomoku-room">
      <View className="gomoku-room-heading">
        <View><Text className="gomoku-kicker">COUPLE GOMOKU</Text><Text className="gomoku-title">{room.mode === "ai" ? "人机五子棋" : "双人五子棋"}</Text></View>
        <View className="gomoku-room-code" onClick={() => Taro.setClipboardData({ data: activeRoomCode })}>
          <Text>{activeRoomCode}</Text><Text>点此复制房间码</Text>
        </View>
      </View>

      <View className={`gomoku-connection ${connectionStatus}`}>
        <View /><Text>{connectionStatus === "online" ? "实时连接正常" : connectionStatus === "connecting" ? "正在连接" : "实时连接已断开"}</Text>
        {connectionStatus === "offline" && <Text onClick={() => connectToRoom(activeRoomCode, { preserveBoard: true })}>重新连接</Text>}
      </View>

      <View className="gomoku-players">
        {[0, 1].map((index) => {
          const player = players[index];
          const color = playerColor(player, index);
          const isCurrent = room.turn_id && room.turn_id === playerIdOf(player);
          return (
            <View key={index} className={`${isCurrent ? "turn" : ""} ${playerIdOf(player) === playerIdRef.current ? "mine" : ""}`}>
              <View className={`gomoku-player-stone ${color}`} />
              <View><Text>{player?.name || (index === 0 ? "等待黑棋" : "等待白棋")}</Text><Text>{colorName(color)}{playerIdOf(player) === playerIdRef.current ? " · 我" : playerIdOf(player)?.startsWith("ai_") ? " · AI" : ""}</Text></View>
              <Text>{isCurrent ? (playerIdOf(player)?.startsWith("ai_") ? "思考中" : "落子中") : player ? "已入座" : "未加入"}</Text>
            </View>
          );
        })}
      </View>

      <View className={`gomoku-turn-message ${isMyTurn ? "mine" : ""}`}><Text>{statusText}</Text><Text>第 {room.round || 1} 局</Text></View>
      {errorMessage && <View className="gomoku-error"><Text>{errorMessage}</Text></View>}

      <GomokuBoard board={room.board || EMPTY_BOARD} lastMove={room.last_move} disabled={!canMove} onMove={submitMove} />

      {players.length < 2 && (
        <View className="gomoku-invite-card">
          <Text>棋桌已经摆好</Text><Text>复制房间码发给女朋友，或者直接分享这个页面。</Text>
          <View className="gomoku-action-row">
            <View onClick={() => Taro.setClipboardData({ data: activeRoomCode })}><Text>复制房间码</Text></View>
            <Button openType="share"><Text>邀请她加入</Text></Button>
          </View>
        </View>
      )}

      {showReady && !isFinished && (
        <View className={`gomoku-primary ${me?.ready ? "disabled" : ""}`} onClick={() => !me?.ready && socketRef.current?.send({ type: "ready" })}>
          <Text>{me?.ready ? "已准备，等待对方" : "我准备好了"}</Text>
        </View>
      )}

      {isFinished && (
        <View className="gomoku-result-mask">
          <View className="gomoku-result-card">
            <Text>{isDraw ? "握手言和" : winnerId === playerIdRef.current ? "这局你赢啦 ♥" : room.mode === "ai" ? "AI 这局更胜一筹" : "这局她更胜一筹"}</Text>
            <Text>{isDraw ? "下一局继续寻找彼此的棋路" : rewardText}</Text>
            <Text>参与本局会记入游戏记录，胜方获得额外默契积分。</Text>
            <View className={`gomoku-primary ${me?.rematch_ready ? "disabled" : ""}`} onClick={() => !me?.rematch_ready && socketRef.current?.send({ type: "rematch" })}>
              <Text>{me?.rematch_ready ? "等待对方再来一局" : "再来一局"}</Text>
            </View>
            <View className="gomoku-result-exit" onClick={returnToGameCenter}><Text>回到游戏大厅</Text></View>
          </View>
        </View>
      )}

      <View className="gomoku-room-footer">
        <Text>红点标记最近一步 · 棋局结果由服务器判定</Text>
        <Text onClick={leaveRoom}>退出房间</Text>
      </View>
    </View>
  );
}
