import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useRouter, useShareAppMessage } from "@tarojs/taro";
import { Button, Input, PageMeta, Text, View } from "@tarojs/components";

import {
  createLandlordRoom,
  getVersionedGameState,
  joinLandlordRoom,
  sendLandlordAction
} from "../../../api";
import LandlordDesk from "../../../components/LandlordDesk";
import LandlordHand from "../../../components/LandlordHand";
import LandlordPlayer from "../../../components/LandlordPlayer";
import GameSyncBar from "../../../components/GameSyncBar";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery, recoverGameRoom } from "../../../utils/gameRecovery";
import useAdaptiveGamePolling from "../../../hooks/useAdaptiveGamePolling";
import "./index.css";

const ROOM_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;
const EMPTY = { phase: "waiting", players: [], names: {}, hand_counts: {}, my_hand: [], bids: [], messages: [] };

/** V2.5 landlord UI; all dealing, rules and AI decisions remain on the server. */
export default function LandlordPage() {
  const router = useRouter();
  const customerId = useRef(getCustomerId()).current;
  const versionRef = useRef(0);
  const roomCodeRef = useRef("");
  const actionLockRef = useRef(false);
  const [allowed, setAllowed] = useState(false);
  const [name, setName] = useState("我");
  const [mode, setMode] = useState("couple");
  const [difficulty, setDifficulty] = useState("rule");
  const [joinCode, setJoinCode] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [version, setVersion] = useState(0);
  const [state, setState] = useState(EMPTY);
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState("");
  const [connection, setConnection] = useState("offline");
  const [syncError, setSyncError] = useState("");

  useEffect(() => {
    if (roomCode) ensureGameRecovery(customerId, roomCode);
  }, [customerId, roomCode]);

  const apply = useCallback((payload) => {
    if (!payload?.state) return;
    if (payload.room_code === roomCodeRef.current && payload.version === versionRef.current) return;
    roomCodeRef.current = payload.room_code || "";
    versionRef.current = payload.version || 0;
    setState(payload.state);
    setVersion(payload.version || 0);
    setRoomCode(payload.room_code || "");
    setSelected([]);
    setConnection("online");
    setSyncError("");
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
      setSyncError(error?.message || "牌桌同步失败");
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
          setSyncError(error?.message || "原牌桌恢复失败");
          Taro.showToast({ title: "原牌桌暂时无法恢复", icon: "none" });
        }
      });
    return () => { cancelled = true; };
  }, [apply, customerId, router.params?.room]);
  useAdaptiveGamePolling({
    enabled: Boolean(roomCode && state.mode !== "ai" && state.phase !== "finished"),
    load: () => refresh(true, true),
    interval: state.phase === "waiting" ? 2400 : 1200,
    onStatus: setConnection,
    onError: (error) => setSyncError(error?.message || "牌桌同步失败")
  });

  useShareAppMessage(() => ({
    title: roomCode ? `来和我斗地主，房间 ${roomCode}` : "来玩一局情侣斗地主",
    path: `/pages/games/landlord/index${roomCode ? `?room=${roomCode}` : ""}`
  }));

  const create = async () => {
    if (actionLockRef.current || busy) return;
    actionLockRef.current = true;
    setBusy("create");
    try { apply(await createLandlordRoom(customerId, name, difficulty, "", mode)); }
    catch (error) { Taro.showToast({ title: error.message || "创建失败", icon: "none" }); }
    finally { actionLockRef.current = false; setBusy(""); }
  };
  const join = async () => {
    const code = joinCode.trim().toUpperCase();
    if (!ROOM_PATTERN.test(code)) return Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
    if (actionLockRef.current || busy) return;
    actionLockRef.current = true;
    setBusy("join");
    try { apply(await joinLandlordRoom(customerId, code, name, "")); }
    catch (error) { Taro.showToast({ title: error.message || "加入失败", icon: "none" }); }
    finally { actionLockRef.current = false; setBusy(""); }
  };
  const act = async (action, data = {}) => {
    if (actionLockRef.current || busy || !version) return;
    actionLockRef.current = true;
    setBusy(action);
    try {
      apply(await sendLandlordAction(customerId, roomCode, version, action, data));
      Taro.vibrateShort({ type: action === "PLAY" ? "medium" : "light" }).catch(() => {});
    } catch (error) {
      Taro.showToast({ title: error.message || "操作失败，请同步后重试", icon: "none" });
      refresh();
    } finally { actionLockRef.current = false; setBusy(""); }
  };

  const toggle = (id) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const useHint = () => {
    const hint = state.suggested_card_ids || [];
    if (!canAct || state.phase !== "playing") return;
    if (!hint.length) {
      Taro.showToast({ title: "这手牌压不过，建议不出", icon: "none" });
      return;
    }
    setSelected(hint);
    Taro.vibrateShort({ type: "light" }).catch(() => {});
  };
  const isMyTurn = state.turn_id === customerId;
  const canAct = connection === "online" && isMyTurn && !busy;
  const canPass = canAct && Boolean(state.last_play) && state.last_play?.player_id !== customerId;
  const opponents = (state.players || []).filter((id) => id !== customerId);
  const status = useMemo(() => {
    if (state.phase === "waiting") return "等她加入后，由服务器洗牌发牌";
    if (state.phase === "bidding") return isMyTurn ? "轮到你决定要不要当地主" : `等待 ${state.names?.[state.turn_id] || "对方"} 叫地主`;
    if (state.phase === "finished") return state.winner_id === customerId ? "你先出完手牌，赢啦 ♥" : `${state.names?.[state.winner_id] || "对方"} 赢得本局`;
    return isMyTurn ? "轮到你出牌" : `等待 ${state.names?.[state.turn_id] || "对方"} 出牌`;
  }, [customerId, isMyTurn, state]);

  if (!allowed) return <><PageMeta pageOrientation="landscape" /><View className="ll-loading"><Text>正在返回邀请码页面…</Text></View></>;
  if (!roomCode) return (
    <>
      <PageMeta pageOrientation="landscape" />
      <View className="ll-page ll-lobby">
      <View className="ll-lobby-back" onClick={() => Taro.switchTab({ url: "/pages/games/index" })}><Text>‹</Text><Text>一起玩</Text></View>
      <View className="ll-hero"><Text>COUPLE LANDLORD</Text><Text>今晚谁是地主</Text><Text>选模式，点开局。洗牌、发牌和胜负都由服务器判断。</Text><View><Text>♠</Text><Text>♥</Text><Text>♣</Text><Text>♦</Text></View></View>
      <View className="ll-lobby-card">
        <View className="ll-lobby-title"><Text>{mode === "ai" ? "单人快速开局" : "创建情侣牌桌"}</Text><Text>{mode === "ai" ? "立即开始" : "建房后邀请她"}</Text></View>
        <Button
          className="ll-main-button"
          disabled={Boolean(busy)}
          hoverClass="ll-main-button-pressed"
          role="button"
          aria-label="开始斗地主"
          onClick={create}
        >
          <View><Text>{busy === "create" ? "正在洗牌…" : mode === "ai" ? "立即开局 · 人机斗地主" : "创建牌桌 · 邀请她"}</Text><Text>{mode === "ai" ? "你和两位 AI，选好即发牌" : "你们两人加一位 AI，建房后分享"}</Text></View>
        </Button>
        <View className="ll-lobby-settings">
          <View className="ll-setting-block"><Text>牌桌称呼</Text><View className="ll-choice-row">{["我", "男朋友", "女朋友"].map((item) => <View key={item} className={name === item ? "active" : ""} onClick={() => setName(item)}><Text>{item}</Text></View>)}</View></View>
          <View className="ll-setting-block"><Text>游戏模式</Text><View className="ll-mode-row"><View className={mode === "couple" ? "active" : ""} onClick={() => setMode("couple")}><Text>情侣牌桌</Text><Text>两人 + 1 AI</Text></View><View className={mode === "ai" ? "active" : ""} onClick={() => setMode("ai")}><Text>人机挑战</Text><Text>你 + 2 AI</Text></View></View></View>
          <View className="ll-setting-block"><Text>AI 风格</Text><View className="ll-choice-row">{[["random", "轻松"], ["rule", "规则"], ["strategy", "高手"]].map(([value, label]) => <View key={value} className={difficulty === value ? "active" : ""} onClick={() => setDifficulty(value)}><Text>{label}</Text></View>)}</View></View>
        </View>
        <View className="ll-join-line"><Text>加入她的牌桌</Text><View className="ll-join"><Input value={joinCode} maxlength={6} placeholder="输入 6 位房间码" onInput={(event) => setJoinCode(event.detail.value.toUpperCase())} onConfirm={join} /><View onClick={join}><Text>{busy === "join" ? "加入中" : "加入"}</Text></View></View></View>
        <Text className="ll-rules">单张、对子、顺子、飞机、炸弹等规则由服务器统一判断，手牌只对本人可见。</Text>
      </View>
      </View>
    </>
  );

  return (
    <>
      <PageMeta pageOrientation="landscape" />
      <View className="ll-page ll-room">
      <View className="ll-table-glow" />
      <View className="ll-room-head">
        <View className="ll-room-left"><Text onClick={() => Taro.switchTab({ url: "/pages/games/index" })}>‹</Text><Text>房间 {roomCode}</Text><Text onClick={() => Taro.setClipboardData({ data: roomCode })}>复制</Text></View>
        <GameSyncBar compact status={connection} message={syncError} onRetry={() => refresh()} />
        <View className="ll-room-tools"><Text>V{version}</Text><Text onClick={() => refresh()}>同步</Text><Text onClick={() => Taro.switchTab({ url: "/pages/games/index" })}>退出</Text></View>
      </View>
      <View className="ll-status"><Text>{status}</Text><Text>{state.landlord_id ? `地主：${state.names?.[state.landlord_id] || "AI"}` : "叫地主阶段"}</Text></View>
      <View className="ll-opponents">{opponents.map((id) => <LandlordPlayer key={id} name={state.names?.[id]} count={state.hand_counts?.[id] || 0} active={state.turn_id === id} landlord={state.landlord_id === id} ai={id.startsWith("ai_")} />)}</View>
      <LandlordDesk play={state.last_play} name={state.names?.[state.last_play?.player_id]} />
      <View className="ll-action-zone">
        {state.phase === "waiting" && <View className="ll-wait"><View><Text>牌桌已准备好</Text><Text>她加入后会自动收到 17 张牌</Text></View><Button openType="share">邀请她加入</Button></View>}
        {state.phase === "bidding" && isMyTurn && <View className="ll-bid-actions"><View className={!canAct ? "disabled" : ""} onClick={() => canAct && act("BID", { bid: false })}><Text>{busy === "BID" ? "确认中…" : connection !== "online" ? "等待同步" : "不叫"}</Text></View><View className={!canAct ? "disabled" : ""} onClick={() => canAct && act("BID", { bid: true })}><Text>{busy === "BID" ? "确认中…" : connection !== "online" ? "等待同步" : "叫地主"}</Text></View></View>}
        {state.phase === "playing" && <View className="ll-play-actions three"><View className={!canAct ? "disabled" : ""} onClick={() => canAct && useHint()}><Text>{selected.length ? "换一组" : "提示"}</Text></View><View className={!canPass ? "disabled" : ""} onClick={() => canPass && act("PASS")}><Text>{busy === "PASS" ? "确认中…" : "不出"}</Text></View><View className={!canAct || !selected.length ? "disabled" : ""} onClick={() => canAct && selected.length && act("PLAY", { card_ids: selected })}><Text>{busy === "PLAY" ? "出牌中…" : connection !== "online" ? "等待同步" : selected.length ? `出这 ${selected.length} 张` : "先选牌"}</Text></View></View>}
      </View>
      <LandlordHand cards={state.my_hand || []} selected={selected} disabled={!canAct || state.phase !== "playing"} onToggle={toggle} />
      <View className="ll-me"><Text>{state.names?.[customerId] || "我"}{state.landlord_id === customerId ? " · 地主" : ""}</Text><Text>{state.hand_counts?.[customerId] || 0} 张</Text></View>
      {state.phase === "finished" && <View className="ll-result"><Text>{status}</Text><Text>参与 +1 · 胜利 +5 · AI 胜利加成 +2</Text><View onClick={() => { setRoomCode(""); setState(EMPTY); }}><Text>再开一桌</Text></View></View>}
      </View>
    </>
  );
}
