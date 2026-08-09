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
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery } from "../../../utils/gameRecovery";
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
  const [allowed, setAllowed] = useState(false);
  const [playerName, setPlayerName] = useState("我");
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
    if (response?.state) setState(response.state);
    if (response?.room_code) setRoomCode(response.room_code);
    setConnection("online");
    setError("");
  }, []);

  const refresh = useCallback(async (silent = false) => {
    if (!roomCode) return;
    if (!silent) setConnection("syncing");
    try {
      applyResponse(await getFlightState(customerIdRef.current, roomCode));
    } catch (requestError) {
      setConnection("offline");
      setError(requestError.message || "棋局同步失败");
    }
  }, [applyResponse, roomCode]);

  useEffect(() => {
    const passed = ensureInvitePassed();
    setAllowed(passed);
    const sharedRoom = String(router.params?.room || "").trim().toUpperCase();
    if (sharedRoom) setJoinCode(sharedRoom);
  }, [router.params?.room]);

  useEffect(() => {
    if (!roomCode) return undefined;
    getCoupleScore(customerIdRef.current).then((result) => setScore(result.total || result.points_total || 0)).catch(() => {});
    const timer = setInterval(() => refresh(true), 2200);
    return () => clearInterval(timer);
  }, [refresh, roomCode]);

  useShareAppMessage(() => ({
    title: roomCode ? `来和我玩情侣飞行棋，房间 ${roomCode}` : "来和我玩一局情侣飞行棋",
    path: `/pages/games/flight/index${roomCode ? `?room=${roomCode}` : ""}`
  }));

  const createRoom = async () => {
    if (busy) return;
    setBusy("create");
    try {
      const result = await createFlightRoom(customerIdRef.current, playerName, "");
      applyResponse(result);
      Taro.showToast({ title: "房间已创建", icon: "success" });
    } catch (requestError) {
      Taro.showToast({ title: requestError.message || "创建失败", icon: "none" });
    } finally {
      setBusy("");
    }
  };

  const joinRoom = async () => {
    const normalized = joinCode.trim().toUpperCase();
    if (!ROOM_PATTERN.test(normalized)) {
      Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
      return;
    }
    if (busy) return;
    setBusy("join");
    try {
      applyResponse(await joinFlightRoom(customerIdRef.current, normalized, playerName, ""));
      Taro.showToast({ title: "已加入棋局", icon: "success" });
    } catch (requestError) {
      Taro.showToast({ title: requestError.message || "加入失败", icon: "none" });
    } finally {
      setBusy("");
    }
  };

  const act = async (action, pieceIndex) => {
    if (busy) return;
    setBusy(action);
    try {
      if (action === "ROLL_DICE") Taro.vibrateShort({ type: "medium" }).catch(() => {});
      const previousTurn = state.turn_id;
      const result = await sendFlightAction(customerIdRef.current, roomCode, action, pieceIndex);
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
    return `等待 ${opponent?.name || "对方"} 掷骰子`;
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
          <View className={`flight-primary ${busy ? "disabled" : ""}`} onClick={createRoom}><Text>{busy === "create" ? "正在准备跑道…" : "创建飞行棋房间"}</Text></View>
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
      <View className="flight-status-card">
        <View className={connection}><Text>{connection === "online" ? "● 已同步" : "● 同步中"}</Text><Text>第 {state.round || 1} 局</Text></View>
        <Text>{statusText}</Text>
        <Text>{me?.name || "我"} · 红色飞机　VS　{opponent?.name || "等待加入"} · 蓝色飞机</Text>
      </View>

      <FlightBoard state={state} meId={customerIdRef.current} onPiece={(index) => act("MOVE_PIECE", index)} />

      {!isFinished && (
        <View className="flight-action-panel">
          <DiceButton value={state.dice} disabled={!canRoll} loading={busy === "ROLL_DICE"} onClick={() => act("ROLL_DICE")} />
          {state.movable?.length > 0 && isMyTurn && <Text>请点击棋盘上正在跳动的飞机。掷出 6 后还可以再来一次。</Text>}
          {!isMyTurn && <Text>棋局每 2 秒自动同步，也可以点上方状态手动刷新。</Text>}
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
