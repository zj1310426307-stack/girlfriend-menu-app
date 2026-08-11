import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useRouter, useShareAppMessage } from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import {
  createFlightRoom,
  getCoupleScore,
  getFlightState,
  joinFlightRoom,
  sendFlightAction
} from "../../../api";
import DiceButton from "../../../components/DiceButton";
import EventPopup from "../../../components/EventPopup";
import FlightBoard from "../../../components/FlightBoard";
import GameSyncBar from "../../../components/GameSyncBar";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery, recoverGameRoom } from "../../../utils/gameRecovery";
import useAdaptiveGamePolling from "../../../hooks/useAdaptiveGamePolling";
import "./index.css";

const ROOM_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;
const EMPTY_STATE = {
  phase: "waiting", players: [], pieces: {}, turn_id: null, dice: null,
  movable: [], pending_event: null, winner_id: null, round: 1
};
const idOf = (player) => player?.id || player?.player_id;

export default function FlightPage() {
  const router = useRouter();
  const customerIdRef = useRef(getCustomerId());
  const revisionRef = useRef("");
  const actionLockRef = useRef(false);
  const [allowed, setAllowed] = useState(false);
  const [playerName, setPlayerName] = useState("我");
  const [mode, setMode] = useState("couple");
  const [difficulty, setDifficulty] = useState("rule");
  const [joinCode, setJoinCode] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [state, setState] = useState(EMPTY_STATE);
  const [busy, setBusy] = useState("");
  const [connection, setConnection] = useState("offline");
  const [score, setScore] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (roomCode) ensureGameRecovery(customerIdRef.current, roomCode);
  }, [roomCode]);

  const me = (state.players || []).find((player) => idOf(player) === customerIdRef.current);
  const opponent = (state.players || []).find((player) => idOf(player) !== customerIdRef.current);
  const isMyTurn = state.phase === "playing" && state.turn_id === customerIdRef.current;
  const isFinished = state.phase === "finished";
  const pendingForMe = state.pending_event?.player_id === customerIdRef.current ? state.pending_event : null;
  const canRoll = isMyTurn && state.dice == null && !state.pending_event && !busy;

  const applyResponse = useCallback((response) => {
    const revision = String(response?.updated_at || "");
    if (response?.state && (!revision || revision !== revisionRef.current)) {
      revisionRef.current = revision;
      setState(response.state);
    }
    if (response?.room_code) setRoomCode(response.room_code);
    setConnection("online");
    setError("");
  }, []);

  const refresh = useCallback(async (silent = false, propagate = false) => {
    if (!roomCode) return;
    if (!silent) setConnection("syncing");
    try {
      applyResponse(await getFlightState(customerIdRef.current, roomCode));
    } catch (requestError) {
      setConnection("offline");
      setError(requestError.message || "棋局同步失败");
      if (propagate) throw requestError;
    }
  }, [applyResponse, roomCode]);

  useEffect(() => {
    const passed = ensureInvitePassed();
    setAllowed(passed);
    const sharedRoom = String(router.params?.room || "").trim().toUpperCase();
    if (!sharedRoom || !ROOM_PATTERN.test(sharedRoom)) return undefined;
    setJoinCode(sharedRoom);
    if (!passed) return undefined;
    let cancelled = false;
    setConnection("syncing");
    recoverGameRoom(
      customerIdRef.current,
      sharedRoom,
      (code) => getFlightState(customerIdRef.current, code)
    ).then((payload) => {
      if (!cancelled && payload) applyResponse(payload);
    }).catch((requestError) => {
      if (cancelled) return;
      setConnection("offline");
      if (requestError?.statusCode !== 403) {
        setError(requestError.message || "原棋局恢复失败");
        Taro.showToast({ title: "原棋局暂时无法恢复", icon: "none" });
      }
    });
    return () => { cancelled = true; };
  }, [applyResponse, router.params?.room]);

  useEffect(() => {
    if (!roomCode) return;
    getCoupleScore(customerIdRef.current).then((result) => setScore(result.total || result.points_total || 0)).catch(() => {});
  }, [roomCode]);
  useAdaptiveGamePolling({
    enabled: Boolean(roomCode && state.mode !== "ai" && state.phase !== "finished"),
    load: () => refresh(true, true),
    interval: state.phase === "waiting" ? 2400 : 1200,
    onStatus: setConnection,
    onError: (requestError) => setError(requestError?.message || "棋局同步失败")
  });

  useShareAppMessage(() => ({
    title: roomCode ? `来和我玩情侣飞行棋，房间 ${roomCode}` : "来和我玩一局情侣飞行棋",
    path: `/pages/games/flight/index${roomCode ? `?room=${roomCode}` : ""}`
  }));

  const createRoom = async () => {
    if (actionLockRef.current || busy) return;
    actionLockRef.current = true;
    setBusy("create");
    try {
      const result = await createFlightRoom(
        customerIdRef.current, playerName, "", mode, difficulty
      );
      applyResponse(result);
      Taro.showToast({ title: mode === "ai" ? "AI 已就位" : "房间已创建", icon: "success" });
    } catch (requestError) {
      Taro.showToast({ title: requestError.message || "创建失败", icon: "none" });
    } finally {
      actionLockRef.current = false;
      setBusy("");
    }
  };

  const joinRoom = async () => {
    const normalized = joinCode.trim().toUpperCase();
    if (!ROOM_PATTERN.test(normalized)) {
      Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
      return;
    }
    if (actionLockRef.current || busy) return;
    actionLockRef.current = true;
    setBusy("join");
    try {
      applyResponse(await joinFlightRoom(customerIdRef.current, normalized, playerName, ""));
      Taro.showToast({ title: "已加入棋局", icon: "success" });
    } catch (requestError) {
      Taro.showToast({ title: requestError.message || "加入失败", icon: "none" });
    } finally {
      actionLockRef.current = false;
      setBusy("");
    }
  };

  const act = async (action, pieceIndex) => {
    if (actionLockRef.current || busy) return;
    actionLockRef.current = true;
    setBusy(action);
    try {
      if (action === "ROLL_DICE") Taro.vibrateShort({ type: "medium" }).catch(() => {});
      const previousTurn = state.turn_id;
      const result = await sendFlightAction(
        customerIdRef.current,
        roomCode,
        action,
        pieceIndex,
        Number(state.version || 1)
      );
      applyResponse(result);
      if (action === "ROLL_DICE" && result.state.dice == null && result.state.turn_id !== previousTurn) {
        Taro.showToast({ title: "没有可移动的棋子，轮到对方", icon: "none" });
      }
      if (action === "MOVE_PIECE") Taro.vibrateShort({ type: "light" }).catch(() => {});
      if (action === "COMPLETE_EVENT") {
        getCoupleScore(customerIdRef.current).then((next) => setScore(next.total || next.points_total || 0)).catch(() => {});
      }
    } catch (requestError) {
      Taro.showToast({ title: requestError.message || "操作失败", icon: "none" });
      refresh(true);
    } finally {
      actionLockRef.current = false;
      setBusy("");
    }
  };

  const statusText = useMemo(() => {
    if (connection === "syncing") return "正在同步两个人的棋盘…";
    if (connection === "offline") return error || "棋盘暂时离线";
    if ((state.players || []).length < 2) return "等待女朋友输入房间码加入";
    if (isFinished) return state.winner_id === customerIdRef.current ? "四架飞机全部到达，你赢啦 ♥" : `${opponent?.name || "对方"} 先到达终点`;
    if (state.pending_event) return state.pending_event.player_id === customerIdRef.current ? "完成互动后继续飞行" : "等待对方完成互动任务";
    if (isMyTurn && state.dice != null) return "选择一架发光的飞机移动";
    if (isMyTurn) return "轮到你掷骰子";
    return state.mode === "ai" ? "AI 正在规划航线…" : `等待 ${opponent?.name || "对方"} 掷骰子`;
  }, [connection, error, isFinished, isMyTurn, opponent?.name, state.dice, state.pending_event, state.players, state.winner_id]);

  if (!allowed) return <View className="flight-loading"><Text>正在返回邀请码页面…</Text></View>;

  if (!roomCode) {
    return (
      <View className="flight-page flight-lobby">
        <View className="flight-lobby-hero">
          <Text>COUPLE FLIGHT</Text>
          <Text>一起飞向终点</Text>
          <Text>服务器掷骰、双人四棋子，途中还会遇到只属于两个人的随机互动。</Text>
          <View className="flight-clouds"><Text>♥</Text><Text>✈</Text><Text>♥</Text></View>
        </View>
        <View className="flight-lobby-card">
          <Text className="flight-lobby-label">我在棋局里的名字</Text>
          <View className="flight-name-options">
            {["我", "男朋友", "女朋友"].map((name) => <View key={name} className={playerName === name ? "active" : ""} onClick={() => setPlayerName(name)}><Text>{name}</Text></View>)}
          </View>
          <Text className="flight-lobby-label">游戏模式</Text>
          <View className="flight-mode-options">
            <View className={mode === "couple" ? "active" : ""} onClick={() => setMode("couple")}><Text>情侣双人</Text><Text>房间码邀请她</Text></View>
            <View className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}><Text>人机练习</Text><Text>立即开始</Text></View>
          </View>
          {mode === "ai" && <View className="flight-difficulty"><Text className={difficulty === "random" ? "active" : ""} onClick={() => setDifficulty("random")}>轻松 AI</Text><Text className={difficulty === "rule" ? "active" : ""} onClick={() => setDifficulty("rule")}>聪明 AI</Text><Text className={difficulty === "strategy" ? "active" : ""} onClick={() => setDifficulty("strategy")}>航线高手</Text></View>}
          <View className={`flight-primary ${busy ? "disabled" : ""}`} onClick={createRoom}><Text>{busy === "create" ? "正在准备跑道…" : mode === "ai" ? "开始人机飞行棋" : "创建飞行棋房间"}</Text></View>
          <Text className="flight-or">或者加入对方的房间</Text>
          <View className="flight-join-row">
            <Input value={joinCode} maxlength={6} placeholder="输入 6 位房间码" onInput={(event) => setJoinCode(event.detail.value.toUpperCase())} onConfirm={joinRoom} />
            <View onClick={joinRoom}><Text>{busy === "join" ? "加入中" : "加入"}</Text></View>
          </View>
          <Text className="flight-rule-note">掷出 6 才能起飞；必须精确到达终点。事件奖励与每日任务均由后端防重复结算。</Text>
        </View>
      </View>
    );
  }

  return (
    <View className="flight-page flight-room-page">
      <View className="flight-room-top">
        <View><Text>房间 {roomCode}</Text><Text onClick={() => Taro.setClipboardData({ data: roomCode })}>复制</Text></View>
        <View><Text>♥ 默契值</Text><Text>{score}</Text></View>
      </View>
      <GameSyncBar status={connection} message={error} onRetry={() => refresh()} />
      <View className="flight-status-card">
        <View><Text>服务器权威棋局</Text><Text>第 {state.round || 1} 局</Text></View>
        <Text>{statusText}</Text>
        <Text>{me?.name || "我"} · 红色飞机　VS　{opponent?.name || "等待加入"} · 蓝色飞机</Text>
      </View>

      <FlightBoard state={state} meId={customerIdRef.current} onPiece={(index) => act("MOVE_PIECE", index)} />

      {!isFinished && (
        <View className="flight-action-panel">
          <DiceButton value={state.dice} disabled={!canRoll} loading={busy === "ROLL_DICE"} onClick={() => act("ROLL_DICE")} />
          {state.movable?.length > 0 && isMyTurn && <Text>请点击棋盘上正在跳动的飞机。掷出 6 后还可以再来一次。</Text>}
          {!isMyTurn && <Text>{state.mode === "ai" ? "AI 行动由服务器完成，请稍等片刻。" : "棋局会自动同步，也可以点下方立即同步。"}</Text>}
          {state.ai_turn_summary?.length > 0 && <Text>AI 最近掷出 {state.ai_turn_summary[state.ai_turn_summary.length - 1].dice} 点</Text>}
        </View>
      )}

      {isFinished && (
        <View className="flight-result-card">
          <Text>{state.winner_id === customerIdRef.current ? "这一程你先到啦" : "她先飞到终点啦"}</Text>
          <Text>参与 +1 · 胜利 +5 · 今日游戏任务自动点亮</Text>
          <View onClick={() => { setRoomCode(""); setState(EMPTY_STATE); }}><Text>再开一个房间</Text></View>
        </View>
      )}

      <View className="flight-room-footer"><Text onClick={() => refresh()}>立即同步</Text><Text onClick={() => Taro.switchTab({ url: "/pages/games/index" })}>返回一起玩</Text></View>
      <EventPopup event={pendingForMe} loading={busy === "COMPLETE_EVENT"} onComplete={() => act("COMPLETE_EVENT")} />
    </View>
  );
}
