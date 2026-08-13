import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useRouter, useShareAppMessage } from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import { createChessRoom, getVersionedGameState, joinChessRoom, sendChessMove } from "../../../api";
import ChessBoard from "../../../components/ChessBoard";
import GameSyncBar from "../../../components/GameSyncBar";
import GameTurnGuide from "../../../components/GameTurnGuide";
import MoveHistory from "../../../components/MoveHistory";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery, recoverGameRoom } from "../../../utils/gameRecovery";
import useAdaptiveGamePolling from "../../../hooks/useAdaptiveGamePolling";
import "./index.css";

const ROOM_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;
const EMPTY = { phase: "waiting", players: [], pieces: [], colors: {}, names: {}, move_history: [] };
const position = (x, y) => `${String.fromCharCode(97 + x)}${y + 1}`;

/** V2.6 Chinese-chess page using server-authoritative moves and version checks. */
export default function ChessPage() {
  const router = useRouter();
  const customerId = useRef(getCustomerId()).current;
  const revisionRef = useRef("");
  const actionLockRef = useRef(false);
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
  const [connection, setConnection] = useState("offline");
  const [syncError, setSyncError] = useState("");
  const [pendingMove, setPendingMove] = useState(null);

  useEffect(() => {
    if (roomCode) ensureGameRecovery(customerId, roomCode);
  }, [customerId, roomCode]);

  const apply = useCallback((payload) => {
    if (!payload?.state) return;
    const revision = `${payload.room_code || ""}:${payload.version || 0}`;
    if (revision === revisionRef.current) return;
    revisionRef.current = revision;
    setState(payload.state); setVersion(payload.version || 0); setRoomCode(payload.room_code || ""); setSelectedId("");
    setConnection("online"); setSyncError("");
  }, []);
  const refresh = useCallback(async (silent = false, propagate = false) => {
    if (!roomCode) return;
    if (!silent) setConnection("syncing");
    try {
      apply(await getVersionedGameState(customerId, roomCode));
      setConnection("online"); setSyncError("");
    }
    catch (error) {
      setConnection("offline");
      setSyncError(error?.message || "棋局同步失败");
      if (propagate) throw error;
    }
  }, [apply, customerId, roomCode]);
  useEffect(() => {
    const passed = ensureInvitePassed();
    setAllowed(passed);
    const shared = String(router.params?.room || "").trim().toUpperCase();
    if (!shared || !ROOM_PATTERN.test(shared)) return undefined;
    setJoinCode(shared);
    if (!passed) return undefined;
    let cancelled = false;
    setConnection("syncing");
    recoverGameRoom(customerId, shared, (code) => getVersionedGameState(customerId, code))
      .then((payload) => { if (!cancelled && payload) apply(payload); })
      .catch((error) => {
        if (cancelled) return;
        setConnection("offline");
        if (error?.statusCode !== 403) {
          setSyncError(error?.message || "原棋局恢复失败");
          Taro.showToast({ title: "原棋局暂时无法恢复", icon: "none" });
        }
      });
    return () => { cancelled = true; };
  }, [apply, customerId, router.params?.room]);
  useAdaptiveGamePolling({
    enabled: Boolean(roomCode && state.phase !== "finished" && state.mode !== "ai"),
    load: () => refresh(true, true),
    interval: state.phase === "waiting" ? 2400 : 1200,
    onStatus: setConnection,
    onError: (error) => setSyncError(error?.message || "棋局同步失败")
  });
  useShareAppMessage(() => ({ title: roomCode ? `来和我下一局中国象棋，房间 ${roomCode}` : "来下一局情侣象棋", path: `/pages/games/chess/index${roomCode ? `?room=${roomCode}` : ""}` }));

  const create = async () => {
    if (actionLockRef.current || busy) return;
    actionLockRef.current = true;
    setBusy("create");
    try { apply(await createChessRoom(customerId, name, mode, difficulty, "")); }
    catch (error) { Taro.showToast({ title: error.message || "创建失败", icon: "none" }); }
    finally { actionLockRef.current = false; setBusy(""); }
  };
  const join = async () => {
    const code = joinCode.trim().toUpperCase();
    if (!ROOM_PATTERN.test(code)) return Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
    if (actionLockRef.current || busy) return;
    actionLockRef.current = true;
    setBusy("join");
    try { apply(await joinChessRoom(customerId, code, name, "")); }
    catch (error) { Taro.showToast({ title: error.message || "加入失败", icon: "none" }); }
    finally { actionLockRef.current = false; setBusy(""); }
  };
  const act = async (action, data = {}) => {
    if (actionLockRef.current || busy || !version) return;
    actionLockRef.current = true;
    setBusy(action);
    try {
      apply(await sendChessMove(customerId, roomCode, version, action, data));
      Taro.vibrateShort({ type: "light" }).catch(() => {});
    } catch (error) {
      Taro.showToast({ title: error.message || "落子失败，请同步后重试", icon: "none" });
      refresh();
    } finally { actionLockRef.current = false; setBusy(""); setPendingMove(null); }
  };
  const onCell = (piece, x, y) => {
    if (state.phase !== "playing" || state.turn_id !== customerId || busy || !version) return;
    if (piece?.color === state.my_color) { setSelectedId((current) => current === piece.id ? "" : piece.id); return; }
    if (!selectedId) return Taro.showToast({ title: "请先选择自己的棋子", icon: "none" });
    const selected = state.pieces.find((item) => item.id === selectedId);
    if (selected) {
      setSelectedId("");
      setPendingMove({ pieceId: selected.id, x, y, label: selected.label, color: selected.color });
      act("MOVE", { from_pos: position(selected.x, selected.y), to_pos: position(x, y) });
    }
  };

  const confirmResign = async () => {
    if (state.phase !== "playing" || busy) return;
    const result = await Taro.showModal({
      title: "确认认输吗？",
      content: "认输后本局会立即结束，棋谱和结果都会保留。",
      confirmText: "确认认输",
      confirmColor: "#9f523f"
    });
    if (result.confirm) act("RESIGN");
  };

  const isMyTurn = state.turn_id === customerId;
  const selectedPiece = state.pieces?.find((item) => item.id === selectedId);
  const statusText = useMemo(() => {
    if (state.phase === "finished" && !state.winner_id) {
      const reason = {
        threefold_repetition: "局面三次重复",
        no_progress_limit: "连续多回合没有吃子或兵卒推进",
        move_limit: "达到最大回合数"
      }[state.draw_reason] || "双方议和";
      return `本局和棋 · ${reason}`;
    }
    if (state.phase === "finished" && state.result_reason === "turn_timeout") {
      return state.winner_id === customerId ? "对方超时，你赢得本局" : "本回合超时，本局结束";
    }
    if (state.phase === "waiting") return "等待另一位玩家加入";
    if (state.phase === "finished") return state.winner_id === customerId ? "这一局你赢啦" : `${state.names?.[state.winner_id] || "对方"} 赢得本局`;
    if (state.check_color) return state.check_color === state.my_color ? "将军！请先应将" : "你将军了";
    return isMyTurn ? "轮到你落子" : `等待 ${state.names?.[state.turn_id] || "对方"} 落子`;
  }, [customerId, isMyTurn, state]);
  const turnGuide = useMemo(() => {
    if (busy === "MOVE") return { marker: "…", title: state.mode === "ai" ? "落子已发送，AI 正在应对" : "正在确认落子", detail: "服务器确认后棋盘会自动更新", tone: "busy" };
    if (connection === "syncing") return { marker: "…", title: "正在同步棋局", detail: "同步完成后再继续操作", tone: "busy" };
    if (connection === "offline") return { marker: "!", title: syncError || "棋局暂时离线", detail: "连接恢复前不会提交动作", tone: "danger", actionLabel: "重试", onAction: () => refresh() };
    if (state.phase === "waiting") return { marker: "码", title: `房间 ${roomCode} 已创建`, detail: "直接邀请她，加入后由红方先行", tone: "waiting", shareLabel: "邀请她" };
    if (!isMyTurn) return { marker: "等", title: statusText, detail: "轮到你时棋子会恢复可操作", tone: "waiting" };
    if (selectedPiece) return { marker: selectedPiece.label, title: `已选择${selectedPiece.label}，再点落点`, detail: "再次点击当前棋子可取消选择", tone: state.check_color ? "danger" : "active", actionLabel: "取消", onAction: () => setSelectedId("") };
    return { marker: state.check_color ? "将" : "1", title: state.check_color ? "正在被将军，请先应将" : "先点一枚自己的棋子", detail: "选中后再点目标交叉点", tone: state.check_color ? "danger" : "active" };
  }, [busy, connection, isMyTurn, refresh, roomCode, selectedPiece, state.check_color, state.mode, state.phase, statusText, syncError]);

  if (!allowed) return <View className="chess-loading"><Text>正在返回邀请码页面…</Text></View>;
  if (!roomCode) return (
    <View className="chess-page chess-lobby">
      <View className="chess-hero"><Text>CHU · HAN</Text><Text>认真下一局中国象棋</Text><Text>服务端判定每一步，支持情侣房间和 AI 陪练。棋谱会保存成共同记忆。</Text><View><Text>車</Text><Text>馬</Text><Text>炮</Text><Text>帥</Text></View></View>
      <View className="chess-lobby-card">
        <Text>对局模式</Text>
        <View className="chess-mode"><View className={mode === "couple" ? "active" : ""} onClick={() => setMode("couple")}><Text>情侣双人</Text><Text>创建房间邀请她</Text></View><View className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}><Text>AI 陪练</Text><Text>先练一局再邀请她</Text></View></View>
        <Text>怎么称呼你</Text><View className="chess-names">{["我", "男朋友", "女朋友"].map((item) => <View key={item} className={name === item ? "active" : ""} onClick={() => setName(item)}><Text>{item}</Text></View>)}</View>
        {mode === "ai" && <View className="chess-difficulty"><Text className={difficulty === "random" ? "active" : ""} onClick={() => setDifficulty("random")}>轻松随机</Text><Text className={difficulty === "rule" ? "active" : ""} onClick={() => setDifficulty("rule")}>规则陪练</Text><Text className={difficulty === "strategy" ? "active" : ""} onClick={() => setDifficulty("strategy")}>两步棋手</Text></View>}
        <View className="chess-create" onClick={create}><Text>{busy === "create" ? "正在摆棋…" : mode === "ai" ? "开始 AI 陪练" : "创建情侣棋局"}</Text></View>
        <Text className="chess-or">或者加入她的房间</Text><View className="chess-join"><Input value={joinCode} maxlength={6} placeholder="输入 6 位房间码" onInput={(event) => setJoinCode(event.detail.value.toUpperCase())} onConfirm={join} /><View onClick={join}><Text>{busy === "join" ? "加入中" : "加入"}</Text></View></View>
      </View>
    </View>
  );

  return (
    <View className="chess-page chess-room">
      <View className="chess-room-head"><View><Text>房间 {roomCode}</Text><Text onClick={() => Taro.setClipboardData({ data: roomCode })}>复制</Text></View><Text>V{version}</Text></View>
      <GameSyncBar status={connection} message={syncError} onRetry={() => refresh()} />
      <View className={`chess-status ${state.check_color ? "checking" : ""}`}><Text>{statusText}</Text><Text>你执{state.my_color === "red" ? "红" : "黑"} · {state.move_count || 0} 步 · {state.mode === "ai" ? "AI 陪练" : "情侣对局"}</Text></View>
      {state.phase !== "finished" && <GameTurnGuide {...turnGuide} />}
      <ChessBoard pieces={state.pieces} myColor={state.my_color} selectedId={selectedId} lastMove={state.last_move} pendingMove={pendingMove} disabled={connection !== "online" || !isMyTurn || state.phase !== "playing" || !!busy} onCell={onCell} />
      <MoveHistory moves={state.move_history} names={state.names} />
      {state.phase === "finished" && <View className="chess-result"><Text>{statusText}</Text><Text>参与 +1 · 胜利 +5 · 成就奖励自动结算</Text><View onClick={() => { setRoomCode(""); setState(EMPTY); }}><Text>再来一局</Text></View></View>}
      <View className="chess-footer"><Text onClick={() => refresh()}>同步棋局</Text><Text onClick={confirmResign}>认输</Text><Text onClick={() => Taro.navigateTo({ url: "/pages/games/ranking/index" })}>排行榜</Text></View>
    </View>
  );
}
