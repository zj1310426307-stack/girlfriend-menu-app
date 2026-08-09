import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useRouter, useShareAppMessage } from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import { createChessRoom, getVersionedGameState, joinChessRoom, sendChessMove } from "../../../api";
import ChessBoard from "../../../components/ChessBoard";
import MoveHistory from "../../../components/MoveHistory";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery } from "../../../utils/gameRecovery";
import "./index.css";

const ROOM_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;
const EMPTY = { phase: "waiting", players: [], pieces: [], colors: {}, names: {}, move_history: [] };
const position = (x, y) => `${String.fromCharCode(97 + x)}${y + 1}`;

/** V2.6 Chinese-chess page using server-authoritative moves and version checks. */
export default function ChessPage() {
  const router = useRouter();
  const customerId = useRef(getCustomerId()).current;
  const [allowed, setAllowed] = useState(false);
  const [name, setName] = useState("我");
  const [mode, setMode] = useState("couple");
  const [difficulty, setDifficulty] = useState("rule");
  const [joinCode, setJoinCode] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [version, setVersion] = useState(0);
  const [state, setState] = useState(EMPTY);
  const [selectedId, setSelectedId] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (roomCode) ensureGameRecovery(customerId, roomCode);
  }, [customerId, roomCode]);

  const apply = useCallback((payload) => {
    if (!payload?.state) return;
    setState(payload.state); setVersion(payload.version || 0); setRoomCode(payload.room_code || ""); setSelectedId("");
  }, []);
  const refresh = useCallback(async () => {
    if (!roomCode) return;
    try { apply(await getVersionedGameState(customerId, roomCode)); } catch (_) {}
  }, [apply, customerId, roomCode]);
  useEffect(() => {
    setAllowed(ensureInvitePassed());
    const shared = String(router.params?.room || "").trim().toUpperCase();
    if (shared) setJoinCode(shared);
  }, [router.params?.room]);
  useEffect(() => {
    if (!roomCode || state.phase === "finished" || state.mode === "ai") return undefined;
    const timer = setInterval(refresh, 1600);
    return () => clearInterval(timer);
  }, [refresh, roomCode, state.mode, state.phase]);
  useShareAppMessage(() => ({ title: roomCode ? `来和我下一局中国象棋，房间 ${roomCode}` : "来下一局情侣象棋", path: `/pages/games/chess/index${roomCode ? `?room=${roomCode}` : ""}` }));

  const create = async () => {
    if (busy) return;
    setBusy("create");
    try { apply(await createChessRoom(customerId, name, mode, difficulty, "")); }
    catch (error) { Taro.showToast({ title: error.message || "创建失败", icon: "none" }); }
    finally { setBusy(""); }
  };
  const join = async () => {
    const code = joinCode.trim().toUpperCase();
    if (!ROOM_PATTERN.test(code)) return Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
    if (busy) return;
    setBusy("join");
    try { apply(await joinChessRoom(customerId, code, name, "")); }
    catch (error) { Taro.showToast({ title: error.message || "加入失败", icon: "none" }); }
    finally { setBusy(""); }
  };
  const act = async (action, data = {}) => {
    if (busy || !version) return;
    setBusy(action);
    try {
      apply(await sendChessMove(customerId, roomCode, version, action, data));
      Taro.vibrateShort({ type: "light" }).catch(() => {});
    } catch (error) {
      Taro.showToast({ title: error.message || "落子失败，请同步后重试", icon: "none" });
      refresh();
    } finally { setBusy(""); }
  };
  const onCell = (piece, x, y) => {
    if (state.phase !== "playing" || state.turn_id !== customerId || busy) return;
    if (piece?.color === state.my_color) { setSelectedId(piece.id); return; }
    if (!selectedId) return Taro.showToast({ title: "请先选择自己的棋子", icon: "none" });
    const selected = state.pieces.find((item) => item.id === selectedId);
    if (selected) act("MOVE", { from_pos: position(selected.x, selected.y), to_pos: position(x, y) });
  };

  const isMyTurn = state.turn_id === customerId;
  const statusText = useMemo(() => {
    if (state.phase === "waiting") return "等待另一位玩家加入";
    if (state.phase === "finished") return state.winner_id === customerId ? "这一局你赢啦" : `${state.names?.[state.winner_id] || "对方"} 赢得本局`;
    if (state.check_color) return state.check_color === state.my_color ? "将军！请先应将" : "你将军了";
    return isMyTurn ? "轮到你落子" : `等待 ${state.names?.[state.turn_id] || "对方"} 落子`;
  }, [customerId, isMyTurn, state]);

  if (!allowed) return <View className="chess-loading"><Text>正在返回邀请码页面…</Text></View>;
  if (!roomCode) return (
    <View className="chess-page chess-lobby">
      <View className="chess-hero"><Text>CHU · HAN</Text><Text>认真下一局中国象棋</Text><Text>服务端判定每一步，支持情侣房间和 AI 陪练。棋谱会保存成共同记忆。</Text><View><Text>車</Text><Text>馬</Text><Text>炮</Text><Text>帥</Text></View></View>
      <View className="chess-lobby-card">
        <Text>对局模式</Text>
        <View className="chess-mode"><View className={mode === "couple" ? "active" : ""} onClick={() => setMode("couple")}><Text>情侣双人</Text><Text>创建房间邀请她</Text></View><View className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}><Text>AI 陪练</Text><Text>先练一局再邀请她</Text></View></View>
        <Text>怎么称呼你</Text><View className="chess-names">{["我", "男朋友", "女朋友"].map((item) => <View key={item} className={name === item ? "active" : ""} onClick={() => setName(item)}><Text>{item}</Text></View>)}</View>
        {mode === "ai" && <View className="chess-difficulty"><Text className={difficulty === "random" ? "active" : ""} onClick={() => setDifficulty("random")}>轻松随机</Text><Text className={difficulty === "rule" ? "active" : ""} onClick={() => setDifficulty("rule")}>规则陪练</Text></View>}
        <View className="chess-create" onClick={create}><Text>{busy === "create" ? "正在摆棋…" : mode === "ai" ? "开始 AI 陪练" : "创建情侣棋局"}</Text></View>
        <Text className="chess-or">或者加入她的房间</Text><View className="chess-join"><Input value={joinCode} maxlength={6} placeholder="输入 6 位房间码" onInput={(event) => setJoinCode(event.detail.value.toUpperCase())} onConfirm={join} /><View onClick={join}><Text>{busy === "join" ? "加入中" : "加入"}</Text></View></View>
      </View>
    </View>
  );

  return (
    <View className="chess-page chess-room">
      <View className="chess-room-head"><View><Text>房间 {roomCode}</Text><Text onClick={() => Taro.setClipboardData({ data: roomCode })}>复制</Text></View><Text>V{version}</Text></View>
      <View className={`chess-status ${state.check_color ? "checking" : ""}`}><Text>{statusText}</Text><Text>你执{state.my_color === "red" ? "红" : "黑"} · {state.move_count || 0} 步 · {state.mode === "ai" ? "AI 陪练" : "情侣对局"}</Text></View>
      <ChessBoard pieces={state.pieces} myColor={state.my_color} selectedId={selectedId} lastMove={state.last_move} disabled={!isMyTurn || state.phase !== "playing" || !!busy} onCell={onCell} />
      <MoveHistory moves={state.move_history} names={state.names} />
      {state.phase === "finished" && <View className="chess-result"><Text>{statusText}</Text><Text>参与 +1 · 胜利 +5 · 成就奖励自动结算</Text><View onClick={() => { setRoomCode(""); setState(EMPTY); }}><Text>再来一局</Text></View></View>}
      <View className="chess-footer"><Text onClick={refresh}>同步棋局</Text><Text onClick={() => state.phase === "playing" && act("RESIGN")}>认输</Text><Text onClick={() => Taro.navigateTo({ url: "/pages/games/ranking/index" })}>排行榜</Text></View>
    </View>
  );
}
