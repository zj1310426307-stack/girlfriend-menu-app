import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useRouter, useShareAppMessage } from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import { createAnimalRoom, getVersionedGameState, joinAnimalRoom, sendAnimalMove } from "../../../api";
import AnimalBoard from "../../../components/AnimalBoard";
import MoveHint from "../../../components/MoveHint";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery } from "../../../utils/gameRecovery";
import "./index.css";

const ROOM_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;
const EMPTY = { phase: "waiting", players: [], pieces: [], colors: {}, names: {}, messages: [] };

/** V2.5 Animal Chess page supporting couple rooms and one-player AI. */
export default function AnimalPage() {
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
    const timer = setInterval(refresh, 1700);
    return () => clearInterval(timer);
  }, [refresh, roomCode, state.mode, state.phase]);
  useShareAppMessage(() => ({ title: roomCode ? `来和我玩斗兽棋，房间 ${roomCode}` : "来玩一局情侣斗兽棋", path: `/pages/games/animal/index${roomCode ? `?room=${roomCode}` : ""}` }));

  const create = async () => {
    if (busy) return; setBusy("create");
    try { apply(await createAnimalRoom(customerId, name, mode, difficulty, "")); }
    catch (error) { Taro.showToast({ title: error.message || "创建失败", icon: "none" }); }
    finally { setBusy(""); }
  };
  const join = async () => {
    const code = joinCode.trim().toUpperCase();
    if (!ROOM_PATTERN.test(code)) return Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
    if (busy) return; setBusy("join");
    try { apply(await joinAnimalRoom(customerId, code, name, "")); }
    catch (error) { Taro.showToast({ title: error.message || "加入失败", icon: "none" }); }
    finally { setBusy(""); }
  };
  const act = async (action, data = {}) => {
    if (busy || !version) return; setBusy(action);
    try { apply(await sendAnimalMove(customerId, roomCode, version, action, data)); Taro.vibrateShort({ type: "light" }).catch(() => {}); }
    catch (error) { Taro.showToast({ title: error.message || "行棋失败，请同步后重试", icon: "none" }); refresh(); }
    finally { setBusy(""); }
  };
  const onCell = (piece, x, y) => {
    if (state.phase !== "playing" || state.turn_id !== customerId || busy) return;
    if (piece?.color === state.my_color) return setSelectedId(piece.id);
    if (!selectedId) return Taro.showToast({ title: "请先选择自己的棋子", icon: "none" });
    act("MOVE", { piece_id: selectedId, x, y });
  };

  const isMyTurn = state.turn_id === customerId;
  const opponentId = state.players?.find((item) => item !== customerId);
  const status = useMemo(() => {
    if (state.phase === "waiting") return "等待女朋友加入森林棋局";
    if (state.phase === "finished") return state.winner_id === customerId ? "你先占领兽穴，赢啦 ♥" : `${state.names?.[state.winner_id] || "对方"} 赢得本局`;
    return isMyTurn ? "轮到你行棋" : `等待 ${state.names?.[state.turn_id] || "对方"} 行棋`;
  }, [customerId, isMyTurn, state]);

  if (!allowed) return <View className="animal-loading"><Text>正在返回邀请码页面…</Text></View>;
  if (!roomCode) return (
    <View className="animal-page animal-lobby">
      <View className="animal-hero"><Text>JUNGLE TOGETHER</Text><Text>森林里的默契对决</Text><Text>标准 7×9 棋盘。狮虎跳河、老鼠下水、占领对方兽穴即可获胜。</Text><View><Text>象</Text><Text>狮</Text><Text>虎</Text><Text>鼠</Text></View></View>
      <View className="animal-lobby-card">
        <Text>游戏模式</Text><View className="animal-mode"><View className={mode === "couple" ? "active" : ""} onClick={() => setMode("couple")}><Text>情侣双人</Text><Text>创建房间邀请她</Text></View><View className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}><Text>单人练习</Text><Text>和森林 AI 对战</Text></View></View>
        <Text>我的名字</Text><View className="animal-names">{["我", "男朋友", "女朋友"].map((item) => <View key={item} className={name === item ? "active" : ""} onClick={() => setName(item)}><Text>{item}</Text></View>)}</View>
        {mode === "ai" && <View className="animal-difficulty"><Text onClick={() => setDifficulty("random")} className={difficulty === "random" ? "active" : ""}>轻松随机</Text><Text onClick={() => setDifficulty("rule")} className={difficulty === "rule" ? "active" : ""}>规则 AI</Text></View>}
        <View className="animal-create" onClick={create}><Text>{busy === "create" ? "正在布置棋盘…" : mode === "ai" ? "开始单人练习" : "创建情侣房间"}</Text></View>
        <Text className="animal-or">或者加入她的房间</Text>
        <View className="animal-join"><Input value={joinCode} maxlength={6} placeholder="输入 6 位房间码" onInput={(event) => setJoinCode(event.detail.value.toUpperCase())} onConfirm={join} /><View onClick={join}><Text>{busy === "join" ? "加入中" : "加入"}</Text></View></View>
      </View>
    </View>
  );

  return (
    <View className="animal-page animal-room">
      <View className="animal-room-head"><View><Text>房间 {roomCode}</Text><Text onClick={() => Taro.setClipboardData({ data: roomCode })}>复制</Text></View><Text>V{version}</Text></View>
      <View className="animal-status"><Text>{status}</Text><Text>你是{state.my_color === "blue" ? "蓝方" : "红方"} · 对手 {state.names?.[opponentId] || "等待加入"}</Text></View>
      <AnimalBoard pieces={state.pieces} selectedId={selectedId} disabled={!isMyTurn || state.phase !== "playing" || !!busy} onCell={onCell} />
      <MoveHint selected={selectedId} myTurn={isMyTurn} waiting={state.phase === "waiting"} />
      {state.last_move && <View className="animal-last"><Text>上一手</Text><Text>{state.names?.[state.last_move.player_id] || "对方"} · {state.last_move.piece_id?.split("_")[1]} → ({state.last_move.to.x + 1},{state.last_move.to.y + 1})</Text></View>}
      {state.phase === "finished" && <View className="animal-result"><Text>{status}</Text><Text>参与 +1 · 胜利 +5 · AI 对战额外奖励</Text><View onClick={() => { setRoomCode(""); setState(EMPTY); }}><Text>再来一局</Text></View></View>}
      <View className="animal-footer"><Text onClick={refresh}>立即同步</Text><Text onClick={() => state.phase === "playing" && act("RESIGN")}>认输</Text><Text onClick={() => Taro.switchTab({ url: "/pages/games/index" })}>返回大厅</Text></View>
    </View>
  );
}
