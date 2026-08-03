import { useEffect, useMemo, useRef, useState } from "react";
import Taro, { useDidHide, useDidShow } from "@tarojs/taro";
import { Canvas, Input, Text, View } from "@tarojs/components";

import { createDiceRoom } from "../../api";
import { connectDiceRoom } from "../../api/diceSocket";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed, INVITE_CODE } from "../../utils/invite";
import { createNativeDiceScene } from "../dice/nativeScene";
import "./index.css";

const EMPTY_ROOM = {
  phase: "waiting",
  players: [],
  round: 1,
  current_bid: null,
  turn_id: null,
  my_dice: null,
  all_dice: null,
  outcome: null,
};

const DICE_FACES = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];

function isHigherBid(currentBid, quantity, face) {
  if (quantity < 1 || face < 1 || face > 6) return false;
  if (!currentBid) return true;
  return quantity > currentBid.quantity
    || (quantity === currentBid.quantity && face > currentBid.face);
}

function nextBidOptions(currentBid) {
  const options = [];
  for (let quantity = 1; quantity <= 10; quantity += 1) {
    for (let face = 1; face <= 6; face += 1) {
      if (isHigherBid(currentBid, quantity, face)) options.push({ quantity, face });
    }
  }
  return options.slice(0, 3);
}

function formatBid(bid) {
  return bid ? `${bid.quantity} 个 ${DICE_FACES[bid.face - 1]}（${bid.face}点）` : "还没有人叫骰";
}

function DiceRow({ values, hidden = false }) {
  if (!values?.length) return <Text className="online-dice-wait">等待摇骰</Text>;
  return (
    <View className="online-dice-row">
      {values.map((value, index) => <Text key={`${value}-${index}`}>{hidden ? "?" : value}</Text>)}
    </View>
  );
}

export default function DiceOnline() {
  const [allowed, setAllowed] = useState(false);
  const [playerName, setPlayerName] = useState("我");
  const [joinCode, setJoinCode] = useState("");
  const [activeRoomCode, setActiveRoomCode] = useState("");
  const [room, setRoom] = useState(EMPTY_ROOM);
  const [connectionStatus, setConnectionStatus] = useState("offline");
  const [sceneReady, setSceneReady] = useState(false);
  const [sceneError, setSceneError] = useState("");
  const [rolling, setRolling] = useState(false);
  const [creating, setCreating] = useState(false);
  const [bidQuantity, setBidQuantity] = useState(1);
  const [bidFace, setBidFace] = useState(2);

  const socketRef = useRef(null);
  const sceneRef = useRef(null);
  const playerIdRef = useRef(getCustomerId());

  const me = room.players.find((player) => player.id === playerIdRef.current);
  const opponent = room.players.find((player) => player.id !== playerIdRef.current);
  const isMyTurn = room.phase === "bidding" && room.turn_id === playerIdRef.current;
  const winner = room.players.find((player) => player.id === room.outcome?.winner_id);
  const loser = room.players.find((player) => player.id === room.outcome?.loser_id);
  const quickBids = useMemo(() => nextBidOptions(room.current_bid), [room.current_bid]);
  const canSubmitBid = isMyTurn && isHigherBid(room.current_bid, bidQuantity, bidFace);

  const roomMessage = useMemo(() => {
    if (connectionStatus !== "online") return "正在连接实时房间…";
    if (room.players.length < 2) return "把房间码发给女朋友，等她加入";
    if (room.phase === "rolling") {
      if (me?.rolled) return opponent?.rolled ? "双方都摇好了" : "你已摇好，等待对方";
      return "双方各摇 5 颗骰子，只能看到自己的结果";
    }
    if (room.phase === "bidding") return isMyTurn ? "轮到你叫骰或开盅" : `等待 ${opponent?.name || "对方"} 操作`;
    if (room.phase === "finished") return winner?.id === playerIdRef.current ? "这局你赢啦 ♥" : `${winner?.name || "对方"} 赢了这局`;
    return "等待对方加入";
  }, [connectionStatus, isMyTurn, me, opponent, room.phase, room.players.length, winner]);

  useEffect(() => {
    setAllowed(ensureInvitePassed());
    return () => {
      socketRef.current?.close?.();
      sceneRef.current?.dispose?.();
    };
  }, []);

  useDidHide(() => sceneRef.current?.pause?.());
  useDidShow(() => sceneRef.current?.resume?.());

  useEffect(() => {
    if (!allowed || !activeRoomCode || sceneRef.current) return undefined;
    let cancelled = false;
    let retryTimer;
    const initialize = (attempt = 0) => {
      Taro.createSelectorQuery()
        .select("#online-dice-webgl")
        .node()
        .exec((result) => {
          if (cancelled) return;
          const canvas = result?.[0]?.node;
          if (!canvas && attempt < 5) {
            retryTimer = setTimeout(() => initialize(attempt + 1), 180);
            return;
          }
          if (!canvas) {
            setSceneError("没有找到 3D 骰子画布");
            return;
          }
          try {
            const windowInfo = Taro.getWindowInfo();
            sceneRef.current = createNativeDiceScene({
              canvas,
              width: Math.max(280, windowInfo.windowWidth * (706 / 750)),
              height: Math.max(280, windowInfo.windowWidth * (560 / 750)),
              onImpact: () => Taro.vibrateShort({ type: "light" }).catch(() => {}),
            });
            setSceneReady(true);
          } catch (error) {
            setSceneError(error?.message || "3D 骰子桌初始化失败");
          }
        });
    };
    Taro.nextTick(() => initialize());
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
    };
  }, [activeRoomCode, allowed]);

  useEffect(() => {
    const next = nextBidOptions(room.current_bid)[0];
    if (!next) return;
    setBidQuantity(next.quantity);
    setBidFace(next.face);
  }, [room.current_bid]);

  const connectToRoom = (code) => {
    const normalized = String(code || "").trim().toUpperCase();
    if (!/^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/.test(normalized)) {
      Taro.showToast({ title: "请输入 6 位房间码", icon: "none" });
      return;
    }
    socketRef.current?.close?.();
    setActiveRoomCode(normalized);
    setJoinCode(normalized);
    setRoom(EMPTY_ROOM);
    setConnectionStatus("connecting");
    socketRef.current = connectDiceRoom({
      roomCode: normalized,
      playerId: playerIdRef.current,
      playerName: playerName.trim() || "玩家",
      inviteCode: INVITE_CODE,
      onState: setRoom,
      onStatus: setConnectionStatus,
      onError: (message) => Taro.showToast({ title: message, icon: "none" }),
    });
  };

  const makeRoom = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const result = await createDiceRoom(INVITE_CODE);
      connectToRoom(result.room_code);
    } catch (error) {
      Taro.showToast({ title: error.message || "创建房间失败", icon: "none" });
    } finally {
      setCreating(false);
    }
  };

  const copyRoomCode = () => {
    Taro.setClipboardData({ data: activeRoomCode });
  };

  const rollDice = async () => {
    if (!sceneReady || rolling || me?.rolled || room.phase !== "rolling") return;
    setRolling(true);
    try {
      Taro.vibrateShort({ type: "heavy" }).catch(() => {});
      const values = await sceneRef.current.roll();
      await sceneRef.current.openCup();
      socketRef.current?.send({ type: "roll", values });
    } catch (error) {
      Taro.showToast({ title: error.message || "摇骰失败", icon: "none" });
    } finally {
      setRolling(false);
    }
  };

  const submitBid = () => {
    if (!isMyTurn) return;
    if (!isHigherBid(room.current_bid, bidQuantity, bidFace)) {
      Taro.showToast({ title: "新叫法要比当前叫法更大", icon: "none" });
      return;
    }
    socketRef.current?.send({ type: "bid", quantity: bidQuantity, face: bidFace });
  };

  if (!allowed) return <View className="online-loading"><Text>正在返回邀请码页面…</Text></View>;

  if (!activeRoomCode) {
    return (
      <View className="online-page online-lobby">
        <Text className="online-kicker">COUPLE BATTLE</Text>
        <Text className="online-title">和女朋友玩大话骰</Text>
        <Text className="online-desc">一人创建房间，把 6 位房间码发给另一人。双方实时叫骰和开盅。</Text>
        <View className="online-card">
          <Text className="online-label">我在房间里的名字</Text>
          <View className="online-name-options">
            {["我", "女朋友"].map((name) => (
              <View key={name} className={playerName === name ? "active" : ""} onClick={() => setPlayerName(name)}><Text>{name}</Text></View>
            ))}
          </View>
          <View className="online-primary" onClick={makeRoom}><Text>{creating ? "正在创建…" : "创建双人房间"}</Text></View>
          <Text className="online-or">或者加入已有房间</Text>
          <Input
            className="online-input"
            value={joinCode}
            maxlength={6}
            placeholder="输入 6 位房间码"
            onInput={(event) => setJoinCode(event.detail.value.toUpperCase())}
            onConfirm={() => connectToRoom(joinCode)}
          />
          <View className="online-secondary" onClick={() => connectToRoom(joinCode)}><Text>加入房间</Text></View>
        </View>
      </View>
    );
  }

  return (
    <View className="online-page">
      <View className="online-heading">
        <View>
          <Text className="online-kicker">LIVE COUPLE DICE</Text>
          <Text className="online-title">双人大话骰</Text>
        </View>
        <View className="online-room-code" onClick={copyRoomCode}>
          <Text>房间 {activeRoomCode}</Text>
          <Text>点此复制</Text>
        </View>
      </View>

      <View className="online-scoreboard">
        <View className="online-score-player">
          <Text>{me?.name || playerName}</Text>
          <Text>{me?.score || 0}</Text>
        </View>
        <View className="online-score-round">
          <Text>第 {room.round || 1} 局</Text>
          <Text>先赢更多局的人获胜</Text>
        </View>
        <View className="online-score-player opponent">
          <Text>{opponent?.name || "女朋友"}</Text>
          <Text>{opponent?.score || 0}</Text>
        </View>
      </View>

      <View className="online-players">
        {room.players.map((player) => (
          <View key={player.id} className={player.id === room.turn_id ? "turn" : ""}>
            <Text>{player.id === playerIdRef.current ? `${player.name}（我）` : player.name}</Text>
            <Text>{player.rolled ? "已摇骰" : "等待摇骰"}</Text>
          </View>
        ))}
        {room.players.length < 2 && <View><Text>等待女朋友加入</Text><Text>分享上方房间码</Text></View>}
      </View>

      <View className="online-canvas-shell">
        <Canvas id="online-dice-webgl" canvasId="online-dice-webgl" type="webgl" className="online-canvas" />
        {!sceneReady && <View className="online-canvas-overlay"><Text>{sceneError || "正在布置 3D 骰子桌…"}</Text></View>}
      </View>

      <View className="online-message"><Text>{roomMessage}</Text></View>

      <View className="online-card online-private">
        <Text className="online-kicker">MY PRIVATE DICE</Text>
        <Text className="online-section-title">我的骰子</Text>
        <DiceRow values={room.my_dice} />
      </View>

      <View className="online-card online-controls">
        {room.phase === "rolling" && (
          <View className={`online-primary ${me?.rolled || rolling ? "disabled" : ""}`} onClick={rollDice}>
            <Text>{rolling ? "骰子碰撞中…" : me?.rolled ? "已摇骰，等待对方" : "开始摇骰"}</Text>
          </View>
        )}
        {room.phase === "waiting" && <View className="online-primary disabled"><Text>等待另一位玩家</Text></View>}
        {room.phase === "bidding" && (
          <>
            <View className="online-current-bid">
              <View><Text>桌面当前叫法</Text><Text>{room.current_bid ? "下一手必须加大" : "由你先开口"}</Text></View>
              <Text>{formatBid(room.current_bid)}</Text>
            </View>
            {isMyTurn && quickBids.length > 0 && (
              <View className="online-quick-bids">
                <Text>顺手加码</Text>
                <View>
                  {quickBids.map((bid) => (
                    <Text
                      key={`${bid.quantity}-${bid.face}`}
                      className={bid.quantity === bidQuantity && bid.face === bidFace ? "active" : ""}
                      onClick={() => { setBidQuantity(bid.quantity); setBidFace(bid.face); }}
                    >
                      {bid.quantity}个{bid.face}
                    </Text>
                  ))}
                </View>
              </View>
            )}
            <View className="online-bid-controls">
              <View>
                <Text>我要叫几个</Text>
                <View className="online-stepper">
                  <Text onClick={() => setBidQuantity((value) => Math.max(1, value - 1))}>−</Text>
                  <Text>{bidQuantity}</Text>
                  <Text onClick={() => setBidQuantity((value) => Math.min(10, value + 1))}>+</Text>
                </View>
              </View>
              <View className="online-faces">
                <Text>选择骰子点数</Text>
                <View>{[1, 2, 3, 4, 5, 6].map((face) => (
                  <Text key={face} className={face === bidFace ? "active" : ""} onClick={() => setBidFace(face)}>
                    <Text>{DICE_FACES[face - 1]}</Text><Text>{face}点</Text>
                  </Text>
                ))}</View>
              </View>
            </View>
            <Text className="online-rule-tip">叫其他点数时，1 点可以当万能点；直接叫 1 点时只算真正的 1。</Text>
            <View className="online-action-row">
              <View className={`online-primary ${canSubmitBid ? "" : "disabled"}`} onClick={submitBid}>
                <Text>我叫 · {bidQuantity} 个 {bidFace} 点</Text>
              </View>
              <View className={`online-open ${isMyTurn && room.current_bid ? "" : "disabled"}`} onClick={() => isMyTurn && room.current_bid && socketRef.current?.send({ type: "challenge" })}>
                <Text>开！</Text><Text>不信</Text>
              </View>
            </View>
          </>
        )}
        {room.phase === "finished" && (
          <View className="online-result">
            <Text className="online-section-title">{winner?.id === playerIdRef.current ? "你赢啦 ♥" : `${winner?.name || "对方"} 赢了`}</Text>
            <Text>实际有 {room.outcome?.actual_count} 颗符合叫法，胜者加 1 分</Text>
            {room.players.map((player) => <View key={player.id}><Text>{player.name}{player.id === loser?.id ? " · 本局输家" : ""}</Text><DiceRow values={room.all_dice?.[player.id]} /></View>)}
            <View className="online-primary" onClick={() => socketRef.current?.send({ type: "rematch" })}><Text>{me?.rematch_ready ? "等待对方再来一局" : "再来一局"}</Text></View>
          </View>
        )}
      </View>

      <View className="online-exit" onClick={() => Taro.navigateBack()}><Text>退出房间</Text></View>
    </View>
  );
}
