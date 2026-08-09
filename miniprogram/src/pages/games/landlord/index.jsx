import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useRouter, useShareAppMessage } from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import {
  createLandlordRoom,
  getVersionedGameState,
  joinLandlordRoom,
  sendLandlordAction
} from "../../../api";
import LandlordDesk from "../../../components/LandlordDesk";
import LandlordHand from "../../../components/LandlordHand";
import LandlordPlayer from "../../../components/LandlordPlayer";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import { ensureGameRecovery } from "../../../utils/gameRecovery";
import "./index.css";

const ROOM_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;
const EMPTY = { phase: "waiting", players: [], names: {}, hand_counts: {}, my_hand: [], bids: [], messages: [] };

/** V2.5 landlord UI; all dealing, rules and AI decisions remain on the server. */
export default function LandlordPage() {
  const router = useRouter();
  const customerId = useRef(getCustomerId()).current;
  const [allowed, setAllowed] = useState(false);
  const [name, setName] = useState("我");
  const [difficulty, setDifficulty] = useState("rule");
  const [joinCode, setJoinCode] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [version, setVersion] = useState(0);
  const [state, setState] = useState(EMPTY);
  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (roomCode) ensureGameRecovery(customerId, roomCode);
  }, [customerId, roomCode]);

  const apply = useCallback((payload) => {
    if (!payload?.state) return;
    setState(payload.state);
    setVersion(payload.version || 0);
    setRoomCode(payload.room_code || "");
    setSelected([]);
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
    if (!roomCode || state.phase === "finished") return undefined;
    const timer = setInterval(refresh, 1800);
    return () => clearInterval(timer);
  }, [refresh, roomCode, state.phase]);

  useShareAppMessage(() => ({
    title: roomCode ? `来和我斗地主，房间 ${roomCode}` : "来玩一局情侣斗地主",
    path: `/pages/games/landlord/index${roomCode ? `?room=${roomCode}` : ""}`
  }));

  const create = async () => {
    if (busy) return;
    setBusy("create");
    try { apply(await createLandlordRoom(customerId, name, difficulty, "")); }
    catch (error) { Taro.showToast({ title: error.message || "创建失败", icon: "none" }); }
    finally { setBusy(""); }
  };
  const join = async () => {
    const code = joinCode.trim().toUpperCase();
    if (!ROOM_PATTERN.test(code)) return Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
    if (busy) return;
    setBusy("join");
    try { apply(await joinLandlordRoom(customerId, code, name, "")); }
    catch (error) { Taro.showToast({ title: error.message || "加入失败", icon: "none" }); }
    finally { setBusy(""); }
  };
  const act = async (action, data = {}) => {
    if (busy || !version) return;
    setBusy(action);
    try {
      apply(await sendLandlordAction(customerId, roomCode, version, action, data));
      Taro.vibrateShort({ type: action === "PLAY" ? "medium" : "light" }).catch(() => {});
    } catch (error) {
      Taro.showToast({ title: error.message || "操作失败，请同步后重试", icon: "none" });
      refresh();
    } finally { setBusy(""); }
  };

  const toggle = (id) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const isMyTurn = state.turn_id === customerId;
  const opponents = (state.players || []).filter((id) => id !== customerId);
  const status = useMemo(() => {
    if (state.phase === "waiting") return "等她加入后，由服务器洗牌发牌";
    if (state.phase === "bidding") return isMyTurn ? "轮到你决定要不要当地主" : `等待 ${state.names?.[state.turn_id] || "对方"} 叫地主`;
    if (state.phase === "finished") return state.winner_id === customerId ? "你先出完手牌，赢啦 ♥" : `${state.names?.[state.winner_id] || "对方"} 赢得本局`;
    return isMyTurn ? "轮到你出牌" : `等待 ${state.names?.[state.turn_id] || "对方"} 出牌`;
  }, [customerId, isMyTurn, state]);

  if (!allowed) return <View className="ll-loading"><Text>正在返回邀请码页面…</Text></View>;
  if (!roomCode) return (
    <View className="ll-page ll-lobby">
      <View className="ll-hero"><Text>COUPLE LANDLORD</Text><Text>今晚谁是地主</Text><Text>两位真人加一位 AI。洗牌、发牌、叫地主与胜负全部由服务器判断。</Text><View><Text>♠</Text><Text>♥</Text><Text>♣</Text><Text>♦</Text></View></View>
      <View className="ll-lobby-card">
        <Text>我在牌桌上的名字</Text>
        <View className="ll-choice-row">{["我", "男朋友", "女朋友"].map((item) => <View key={item} className={name === item ? "active" : ""} onClick={() => setName(item)}><Text>{item}</Text></View>)}</View>
        <Text>AI 风格</Text>
        <View className="ll-choice-row two"><View className={difficulty === "random" ? "active" : ""} onClick={() => setDifficulty("random")}><Text>轻松随机</Text></View><View className={difficulty === "rule" ? "active" : ""} onClick={() => setDifficulty("rule")}><Text>规则陪玩</Text></View></View>
        <View className="ll-main-button" onClick={create}><Text>{busy === "create" ? "正在洗牌…" : "创建斗地主房间"}</Text></View>
        <View className="ll-divider"><Text>或者加入她的牌桌</Text></View>
        <View className="ll-join"><Input value={joinCode} maxlength={6} placeholder="输入 6 位房间码" onInput={(event) => setJoinCode(event.detail.value.toUpperCase())} onConfirm={join} /><View onClick={join}><Text>{busy === "join" ? "加入中" : "加入"}</Text></View></View>
        <Text className="ll-rules">当前支持单张、对子、三张、三带一、顺子、炸弹和王炸。手牌只对本人可见。</Text>
      </View>
    </View>
  );

  return (
    <View className="ll-page ll-room">
      <View className="ll-room-head"><View><Text>房间 {roomCode}</Text><Text onClick={() => Taro.setClipboardData({ data: roomCode })}>复制</Text></View><Text>V{version}</Text></View>
      <View className="ll-status"><Text>{status}</Text><Text>{state.landlord_id ? `地主：${state.names?.[state.landlord_id] || "AI"}` : "叫地主阶段"}</Text></View>
      <View className="ll-opponents">{opponents.map((id) => <LandlordPlayer key={id} name={state.names?.[id]} count={state.hand_counts?.[id] || 0} active={state.turn_id === id} landlord={state.landlord_id === id} ai={id.startsWith("ai_")} />)}</View>
      <LandlordDesk play={state.last_play} name={state.names?.[state.last_play?.player_id]} />
      <View className="ll-action-zone">
        {state.phase === "waiting" && <View className="ll-wait"><Text>把房间码发给女朋友</Text><Text>她加入后会自动收到 17 张牌</Text></View>}
        {state.phase === "bidding" && isMyTurn && <View className="ll-bid-actions"><View onClick={() => act("BID", { bid: false })}><Text>不叫</Text></View><View onClick={() => act("BID", { bid: true })}><Text>叫地主</Text></View></View>}
        {state.phase === "playing" && <View className="ll-play-actions"><View className={!isMyTurn ? "disabled" : ""} onClick={() => isMyTurn && act("PASS")}><Text>不出</Text></View><View className={!isMyTurn || !selected.length ? "disabled" : ""} onClick={() => isMyTurn && selected.length && act("PLAY", { card_ids: selected })}><Text>{busy === "PLAY" ? "出牌中…" : `出牌 ${selected.length || ""}`}</Text></View></View>}
      </View>
      <LandlordHand cards={state.my_hand || []} selected={selected} disabled={!isMyTurn || state.phase !== "playing" || !!busy} onToggle={toggle} />
      <View className="ll-me"><Text>{state.names?.[customerId] || "我"}{state.landlord_id === customerId ? " · 地主" : ""}</Text><Text>{state.hand_counts?.[customerId] || 0} 张</Text></View>
      {state.phase === "finished" && <View className="ll-result"><Text>{status}</Text><Text>参与 +1 · 胜利 +5 · AI 胜利加成 +2</Text><View onClick={() => { setRoomCode(""); setState(EMPTY); }}><Text>再开一桌</Text></View></View>}
      <View className="ll-footer"><Text onClick={refresh}>立即同步</Text><Text onClick={() => Taro.switchTab({ url: "/pages/games/index" })}>返回一起玩</Text></View>
    </View>
  );
}
