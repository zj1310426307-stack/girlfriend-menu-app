import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Taro, { useDidHide, useDidShow } from "@tarojs/taro";
import { Canvas, Text, View } from "@tarojs/components";

import { chooseAiAction } from "./aiPlayer";
import {
  createHiddenDice,
  createPlayers,
  DICE_PER_PLAYER,
  formatBid,
  getNextLegalBid,
  getNextPlayer,
  isHigherBid,
  MAX_PLAYERS,
  MIN_PLAYERS,
  resolveChallenge,
} from "./gameLogic";
import { createNativeDiceScene } from "./nativeScene";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const DICE_VERSION = "1.0.17";

const PHASES = {
  ready: "ready",
  rolling: "rolling",
  readyToOpen: "readyToOpen",
  opening: "opening",
  bidding: "bidding",
  finished: "finished",
};

function vibrate(type = "medium") {
  try {
    Taro.vibrateShort({ type });
  } catch {
    // Vibration is decorative; unsupported devices can keep playing.
  }
}

function DiceValues({ values, hidden = false }) {
  if (!values?.length) return <Text className="dice-values-placeholder">等待摇骰</Text>;
  return (
    <View className="dice-value-row">
      {values.map((value, index) => (
        <Text key={`${value}-${index}`}>{hidden ? "?" : value}</Text>
      ))}
    </View>
  );
}

function getTouchY(event) {
  const source = event?.nativeEvent || event?.mpEvent || event;
  const touch =
    source?.touches?.[0] ||
    source?.changedTouches?.[0] ||
    source?.changeTouches?.[0];
  return Number(touch?.clientY ?? touch?.pageY ?? source?.detail?.y ?? 0);
}

export default function DicePage() {
  const [allowed, setAllowed] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [sceneError, setSceneError] = useState("");
  const [playerCount, setPlayerCount] = useState(3);
  const players = useMemo(() => createPlayers(playerCount), [playerCount]);
  const [phase, setPhase] = useState(PHASES.ready);
  const [message, setMessage] = useState("选好人数，开始今晚第一局");
  const [resultsByPlayer, setResultsByPlayer] = useState({});
  const [currentPlayerId, setCurrentPlayerId] = useState("me");
  const [currentBid, setCurrentBid] = useState(null);
  const [bidQuantity, setBidQuantity] = useState(1);
  const [bidFace, setBidFace] = useState(2);
  const [roundOutcome, setRoundOutcome] = useState(null);
  const [history, setHistory] = useState([]);
  const [cupDrag, setCupDrag] = useState(0);
  const [diceBounds, setDiceBounds] = useState({
    maxRadius: 0,
    safeRadius: 0,
    minSeparation: 0,
    maxTilt: 0,
    settleMs: 0,
    physicsSteps: 0,
  });

  const sceneRef = useRef(null);
  const mountedRef = useRef(true);
  const aiTimerRef = useRef(null);
  const gestureRef = useRef(null);
  const pendingResultsRef = useRef({});
  const impactFeedbackRef = useRef({ count: 0, lastAt: 0 });

  const currentPlayer = players.find((player) => player.id === currentPlayerId) || players[0];
  const maxBidQuantity = players.length * DICE_PER_PLAYER;
  const currentBidder = currentBid
    ? players.find((player) => player.id === currentBid.bidderId)
    : null;

  useDidHide(() => {
    sceneRef.current?.pause?.();
  });

  useDidShow(() => {
    sceneRef.current?.resume?.();
  });

  useEffect(() => {
    mountedRef.current = true;
    setAllowed(ensureInvitePassed());
    return () => {
      mountedRef.current = false;
      if (aiTimerRef.current) clearTimeout(aiTimerRef.current);
      sceneRef.current?.dispose?.();
      sceneRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!allowed || sceneRef.current) return undefined;
    let cancelled = false;
    let retryTimer = null;

    const initializeScene = (attempt = 0) => {
      const query = Taro.createSelectorQuery();
      query
        .select("#dice-webgl")
        .node()
        .exec((result) => {
          if (cancelled) return;
          const canvas = result?.[0]?.node;
          if (!canvas) {
            if (attempt < 5) {
              retryTimer = setTimeout(() => initializeScene(attempt + 1), 180);
              return;
            }
            setSceneError(`没有找到 3D 画布（v${DICE_VERSION}），请更新微信后重试`);
            return;
          }
          try {
            const windowInfo = Taro.getWindowInfo();
            const width = Math.max(280, windowInfo.windowWidth * (706 / 750));
            const height = Math.max(300, windowInfo.windowWidth * (690 / 750));
            sceneRef.current = createNativeDiceScene({
              canvas,
              width,
              height,
              onImpact: () => {
                const now = Date.now();
                const feedback = impactFeedbackRef.current;
                if (feedback.count < 3 && now - feedback.lastAt > 260) {
                  feedback.count += 1;
                  feedback.lastAt = now;
                  vibrate("light");
                }
              },
            });
            setSceneReady(true);
          } catch (error) {
            const detail = error?.message || String(error);
            console.error("初始化原生 3D 骰子失败", detail, error?.stack || "");
            setSceneError(`当前设备暂时无法显示 3D 骰子：${detail}`);
          }
        });
    };

    Taro.nextTick(() => initializeScene());

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [allowed]);

  const addHistory = useCallback((entry) => {
    setHistory((items) => [entry, ...items].slice(0, 8));
  }, []);

  const startRound = useCallback(() => {
    if (!sceneRef.current || !sceneReady) {
      Taro.showToast({ title: "3D 桌面还在准备", icon: "none" });
      return;
    }
    if (aiTimerRef.current) clearTimeout(aiTimerRef.current);
    setPhase(PHASES.rolling);
    setMessage("骰盅正在摇动，五颗骰子会自然翻滚…");
    setResultsByPlayer({});
    setCurrentBid(null);
    setCurrentPlayerId("me");
    setBidQuantity(1);
    setBidFace(2);
    setRoundOutcome(null);
    setHistory([]);
    setCupDrag(0);
    setDiceBounds({
      maxRadius: 0,
      safeRadius: 0,
      minSeparation: 0,
      maxTilt: 0,
      settleMs: 0,
      physicsSteps: 0,
    });
    pendingResultsRef.current = {};
    impactFeedbackRef.current = { count: 0, lastAt: 0 };
    vibrate("heavy");

    sceneRef.current
      .roll()
      .then((myValues) => {
        if (!mountedRef.current) return;
        setDiceBounds(sceneRef.current?.getBoundsSnapshot?.() || { maxRadius: 0, safeRadius: 0 });
        const nextResults = {};
        players.forEach((player) => {
          nextResults[player.id] = player.id === "me" ? myValues : createHiddenDice();
        });
        pendingResultsRef.current = nextResults;
        setPhase(PHASES.readyToOpen);
        setMessage("骰子停稳啦，按住桌面向上滑动开盅");
        vibrate("medium");
      })
      .catch((error) => {
        console.error("摇骰失败", error);
        if (mountedRef.current) {
          setPhase(PHASES.ready);
          setMessage("刚才没有摇起来，再试一次吧");
        }
      });
  }, [players, sceneReady]);

  const openCup = useCallback(() => {
    if (phase !== PHASES.readyToOpen || !sceneRef.current) return;
    setPhase(PHASES.opening);
    setMessage("开盅中…");
    setCupDrag(1);
    vibrate("light");
    sceneRef.current.openCup().then(() => {
      if (!mountedRef.current) return;
      setResultsByPlayer(pendingResultsRef.current);
      setPhase(PHASES.bidding);
      setCurrentPlayerId("me");
      setMessage("只看自己的骰子，轮到你先叫");
      addHistory("本局骰子已经停稳并开盅");
      vibrate("medium");
    });
  }, [addHistory, phase]);

  const handleTouchStart = useCallback(
    (event) => {
      if (phase !== PHASES.readyToOpen) return;
      gestureRef.current = { startY: getTouchY(event), currentY: getTouchY(event) };
    },
    [phase],
  );

  const handleTouchMove = useCallback(
    (event) => {
      if (phase !== PHASES.readyToOpen || !gestureRef.current) return;
      const currentY = getTouchY(event);
      gestureRef.current.currentY = currentY;
      const distance = gestureRef.current.startY - currentY;
      const progress = Math.max(0, Math.min(1, distance / 120));
      setCupDrag(progress);
      sceneRef.current?.previewCupLift(progress);
    },
    [phase],
  );

  const handleTouchEnd = useCallback((event) => {
    if (phase !== PHASES.readyToOpen || !gestureRef.current) return;
    const eventEndY = getTouchY(event);
    const endY = eventEndY || gestureRef.current.currentY;
    const distance = gestureRef.current.startY - endY;
    gestureRef.current = null;
    if (distance >= 70) {
      openCup();
      return;
    }
    setCupDrag(0);
    sceneRef.current?.resetCupLift();
    setMessage("再向上滑一点，就能看到点数啦");
  }, [openCup, phase]);

  const finishChallenge = useCallback(
    (challengerId, bid = currentBid) => {
      const outcome = resolveChallenge({
        bid,
        challengerId,
        resultsByPlayer: pendingResultsRef.current,
      });
      if (!outcome) return;
      const challenger = players.find((player) => player.id === challengerId);
      const bidder = players.find((player) => player.id === bid.bidderId);
      const loser = players.find((player) => player.id === outcome.loserId);
      setRoundOutcome(outcome);
      setPhase(PHASES.finished);
      setMessage(
        `${challenger.name}开了${bidder.name}：实际有${outcome.actualCount}个${bid.face}，${loser.name}输了`,
      );
      addHistory(`${challenger.name}选择开盅，实际${outcome.actualCount}个${bid.face}`);
      vibrate("heavy");
    },
    [addHistory, currentBid, players],
  );

  useEffect(() => {
    if (phase !== PHASES.bidding || !currentPlayer || currentPlayer.isHuman) {
      return undefined;
    }

    setMessage(`${currentPlayer.name}正在想要不要相信你…`);
    aiTimerRef.current = setTimeout(() => {
      const action = chooseAiAction({
        currentBid,
        ownDice: pendingResultsRef.current[currentPlayer.id],
        playerCount: players.length,
      });
      if (action.type === "open") {
        finishChallenge(currentPlayer.id, currentBid);
        return;
      }

      const nextBid = { ...action.bid, bidderId: currentPlayer.id };
      setCurrentBid(nextBid);
      addHistory(`${currentPlayer.name}叫了 ${formatBid(nextBid)}`);
      const nextPlayer = getNextPlayer(players, currentPlayer.id);
      const suggestion = getNextLegalBid(
        nextBid,
        nextBid.quantity,
        nextBid.face + 1,
        maxBidQuantity,
      );
      setCurrentPlayerId(nextPlayer.id);
      setBidQuantity(suggestion?.quantity ?? nextBid.quantity);
      setBidFace(suggestion?.face ?? nextBid.face);
      setMessage(nextPlayer.isHuman ? "轮到你：加数量、加点数，或者开" : `${nextPlayer.name}准备叫骰`);
    }, 760 + Math.random() * 420);

    return () => clearTimeout(aiTimerRef.current);
  }, [
    addHistory,
    currentBid,
    currentPlayer,
    finishChallenge,
    maxBidQuantity,
    phase,
    players,
  ]);

  const submitBid = useCallback(() => {
    const proposedBid = { quantity: bidQuantity, face: bidFace, bidderId: "me" };
    if (!isHigherBid(currentBid, proposedBid)) {
      setMessage(`叫法必须高于 ${formatBid(currentBid)}`);
      vibrate("light");
      return;
    }
    setCurrentBid(proposedBid);
    addHistory(`我叫了 ${formatBid(proposedBid)}`);
    const nextPlayer = getNextPlayer(players, "me");
    setCurrentPlayerId(nextPlayer.id);
    setBidQuantity(proposedBid.quantity);
    setBidFace(proposedBid.face < 6 ? proposedBid.face + 1 : proposedBid.face);
    setMessage(`${nextPlayer.name}正在思考…`);
  }, [addHistory, bidFace, bidQuantity, currentBid, players]);

  const changePlayerCount = useCallback(
    (count) => {
      if (phase !== PHASES.ready && phase !== PHASES.finished) return;
      setPlayerCount(count);
      setPhase(PHASES.ready);
      setCurrentBid(null);
      setResultsByPlayer({});
      setRoundOutcome(null);
      setMessage("人数已调整，开始一局新游戏吧");
    },
    [phase],
  );

  if (!allowed) {
    return (
      <View className="dice-native-loading">
        <Text className="dice-native-heart">♥</Text>
        <Text>正在返回邀请码页面…</Text>
      </View>
    );
  }

  return (
    <View className="dice-native-page">
      <View className="dice-heading">
        <Text className="dice-kicker">BAR DICE · 原生 3D</Text>
        <Text className="dice-title">大话骰 · 吹牛</Text>
        <Text className="dice-subtitle">关掉网页也能玩的酒吧骰子桌 · v{DICE_VERSION}</Text>
      </View>

      <View className="dice-status-card">
        <View>
          <Text>当前玩家</Text>
          <Text className="dice-status-value">
            {phase === PHASES.rolling ? "摇骰中" : currentPlayer.name}
          </Text>
        </View>
        <View className="dice-current-bid">
          <Text>当前叫法</Text>
          <Text className="dice-status-value">{formatBid(currentBid)}</Text>
          {currentBidder && <Text className="dice-status-small">来自 {currentBidder.name}</Text>}
        </View>
      </View>

      <View className="dice-player-picker">
        <Text>玩家人数</Text>
        <View>
          {Array.from(
            { length: MAX_PLAYERS - MIN_PLAYERS + 1 },
            (_, index) => MIN_PLAYERS + index,
          ).map((count) => (
            <View
              key={count}
              className={`dice-player-option ${playerCount === count ? "active" : ""}`}
              onClick={() => changePlayerCount(count)}
            >
              <Text>{count}人</Text>
            </View>
          ))}
        </View>
      </View>

      <View
        className={`dice-canvas-shell ${phase === PHASES.readyToOpen ? "can-open" : ""}`}
        data-dice-max-radius={diceBounds.maxRadius.toFixed(4)}
        data-cup-safe-radius={diceBounds.safeRadius.toFixed(4)}
        data-dice-min-separation={diceBounds.minSeparation.toFixed(4)}
        data-dice-max-tilt={diceBounds.maxTilt.toFixed(4)}
        data-dice-settle-ms={diceBounds.settleMs}
        data-dice-physics-steps={diceBounds.physicsSteps}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchEnd}
      >
        <Canvas id="dice-webgl" canvasId="dice-webgl" type="webgl" className="dice-webgl-canvas" />
        <View className="dice-boundary-metrics">
          <Text>{`${diceBounds.maxRadius.toFixed(4)}|${diceBounds.safeRadius.toFixed(4)}|${diceBounds.minSeparation.toFixed(4)}|${diceBounds.maxTilt.toFixed(4)}|${diceBounds.settleMs}|${diceBounds.physicsSteps}`}</Text>
        </View>
        {sceneReady && (
          <View className="dice-live-badge">
            <Text className="dice-live-dot">●</Text>
            <Text>FIXED-STEP PHYSICS</Text>
          </View>
        )}
        {!sceneReady && !sceneError && (
          <View className="dice-canvas-overlay">
            <Text>正在点亮 3D 骰子桌…</Text>
          </View>
        )}
        {sceneError && (
          <View className="dice-canvas-overlay error">
            <Text>{sceneError}</Text>
          </View>
        )}
        {phase === PHASES.readyToOpen && (
          <View
            className="dice-open-hint"
            style={{ opacity: 1 - cupDrag * 0.55 }}
            onClick={openCup}
          >
            <Text className="dice-open-arrow">↑</Text>
            <Text>向上滑动开盅 · 也可轻触打开</Text>
          </View>
        )}
      </View>

      <View className="dice-scene-message">
        <Text>{message}</Text>
      </View>

      <View className="dice-private-card">
        <View>
          <Text className="dice-kicker">PRIVATE DICE</Text>
          <Text className="dice-section-title">我的骰子</Text>
        </View>
        <DiceValues values={resultsByPlayer.me} />
        {phase === PHASES.bidding && <Text className="dice-private-tip">只有你能看到这一组</Text>}
      </View>

      <View className="dice-control-card">
        {(phase === PHASES.ready || phase === PHASES.finished) && (
          <View className="dice-primary-action" onClick={startRound}>
            <Text>{phase === PHASES.finished ? "再来一局" : "开始摇骰"}</Text>
          </View>
        )}

        {phase === PHASES.rolling && (
          <View className="dice-primary-action disabled"><Text>骰子碰撞中…</Text></View>
        )}

        {(phase === PHASES.readyToOpen || phase === PHASES.opening) && (
          <View className="dice-primary-action disabled">
            <Text>{phase === PHASES.opening ? "正在开盅…" : "向上滑动骰盅"}</Text>
          </View>
        )}

        {phase === PHASES.bidding && currentPlayer.isHuman && (
          <>
            <View className="dice-bid-controls">
              <View className="dice-quantity-control">
                <Text className="dice-control-label">数量</Text>
                <View className="dice-stepper">
                  <View onClick={() => setBidQuantity((value) => Math.max(1, value - 1))}><Text>−</Text></View>
                  <Text>{bidQuantity}</Text>
                  <View onClick={() => setBidQuantity((value) => Math.min(maxBidQuantity, value + 1))}><Text>+</Text></View>
                </View>
              </View>
              <View className="dice-face-control">
                <Text className="dice-control-label">点数</Text>
                <View className="dice-face-options">
                  {[1, 2, 3, 4, 5, 6].map((face) => (
                    <View
                      key={face}
                      className={bidFace === face ? "active" : ""}
                      onClick={() => setBidFace(face)}
                    >
                      <Text>{face}</Text>
                    </View>
                  ))}
                </View>
              </View>
            </View>
            <View className="dice-action-row">
              <View className="dice-primary-action" onClick={submitBid}>
                <Text>叫骰 · {bidQuantity}个{bidFace}</Text>
              </View>
              <View
                className={`dice-open-action ${currentBid ? "" : "disabled"}`}
                onClick={() => currentBid && finishChallenge("me")}
              >
                <Text>开</Text>
              </View>
            </View>
          </>
        )}

        {phase === PHASES.bidding && !currentPlayer.isHuman && (
          <View className="dice-ai-thinking"><Text>● ● ●　{currentPlayer.name} 正在思考</Text></View>
        )}
      </View>

      {roundOutcome && (
        <View className="dice-reveal-card">
          <Text className="dice-kicker">OPEN THE CUP</Text>
          <Text className="dice-section-title">全桌开盅</Text>
          <Text className="dice-outcome-text">{message}</Text>
          <View className="dice-player-results">
            {players.map((player) => (
              <View
                key={player.id}
                className={roundOutcome.loserId === player.id ? "loser" : ""}
              >
                <Text className="dice-result-name">{player.name}</Text>
                <DiceValues values={pendingResultsRef.current[player.id]} />
                {roundOutcome.loserId === player.id && <Text className="dice-loser-tag">本局输家</Text>}
              </View>
            ))}
          </View>
        </View>
      )}

      <View className="dice-rules-card">
        <Text className="dice-kicker">HOW TO PLAY</Text>
        <Text className="dice-section-title">这一桌怎么玩</Text>
        <Text>1. 每人 5 颗骰子，只能看到自己的点数。</Text>
        <Text>2. “3个5”表示全桌至少有 3 颗五，下一位必须加码。</Text>
        <Text>3. 1 点通常作万能点；叫 1 时只统计真正的 1。</Text>
        <Text>4. 不相信上一位就点“开”，系统会立即判断输赢。</Text>
        {history.length > 0 && (
          <View className="dice-history">
            {history.map((entry, index) => <Text key={`${entry}-${index}`}>{entry}</Text>)}
          </View>
        )}
      </View>
    </View>
  );
}
