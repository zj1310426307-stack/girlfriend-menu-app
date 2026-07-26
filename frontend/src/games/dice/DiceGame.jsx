import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { chooseAiAction } from "./aiPlayer";
import DiceScene from "./DiceScene";
import {
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
import {
  playDiceSound,
  setDiceSoundEnabled,
} from "./sounds";
import "./styles.css";

const PHASES = {
  ready: "ready",
  rolling: "rolling",
  bidding: "bidding",
  finished: "finished",
};

/**
 * Gives short tactile feedback without requiring permission on unsupported devices.
 */
function vibrate(pattern) {
  if (typeof navigator !== "undefined" && navigator.vibrate) {
    navigator.vibrate(pattern);
  }
}

/**
 * Renders a compact row of face values.
 */
function DiceValueRow({ values, hidden = false }) {
  if (!values?.length) {
    return <span className="dice-values-placeholder">等待摇骰</span>;
  }
  return (
    <span className="dice-value-row">
      {values.map((value, index) => (
        <i key={index}>{hidden ? "?" : value}</i>
      ))}
    </span>
  );
}

/**
 * Runs the complete local human-versus-AI liar's-dice game.
 */
export default function DiceGame() {
  const [searchParams] = useSearchParams();
  const isWeappEmbed = searchParams.get("embed") === "weapp";
  const [playerCount, setPlayerCount] = useState(3);
  const players = useMemo(() => createPlayers(playerCount), [playerCount]);
  const [roundId, setRoundId] = useState(0);
  const [phase, setPhase] = useState(PHASES.ready);
  const [resultsByPlayer, setResultsByPlayer] = useState({});
  const [currentPlayerId, setCurrentPlayerId] = useState("me");
  const [currentBid, setCurrentBid] = useState(null);
  const [bidQuantity, setBidQuantity] = useState(1);
  const [bidFace, setBidFace] = useState(2);
  const [roundOutcome, setRoundOutcome] = useState(null);
  const [message, setMessage] = useState("选好人数，开始今晚第一局");
  const [history, setHistory] = useState([]);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [motionEnabled, setMotionEnabled] = useState(false);
  const [deviceTilt, setDeviceTilt] = useState({ beta: 0, gamma: 0 });
  const [gestureOffset, setGestureOffset] = useState(0);
  const [gestureActive, setGestureActive] = useState(false);
  const settledRef = useRef({});
  const aiTimerRef = useRef(null);
  const phaseRef = useRef(PHASES.ready);
  const startRoundRef = useRef(null);
  const gestureRef = useRef(null);

  const currentPlayer = players.find((player) => player.id === currentPlayerId) || players[0];
  const maxBidQuantity = players.length * DICE_PER_PLAYER;

  useEffect(() => {
    setDiceSoundEnabled(soundEnabled);
  }, [soundEnabled]);

  useEffect(() => {
    phaseRef.current = phase;
  }, [phase]);

  useEffect(
    () => () => {
      if (aiTimerRef.current) {
        window.clearTimeout(aiTimerRef.current);
      }
    },
    [],
  );

  const addHistory = useCallback((entry) => {
    setHistory((items) => [entry, ...items].slice(0, 8));
  }, []);

  const startRound = useCallback(() => {
    if (aiTimerRef.current) {
      window.clearTimeout(aiTimerRef.current);
    }
    settledRef.current = {};
    setResultsByPlayer({});
    setCurrentBid(null);
    setCurrentPlayerId("me");
    setBidQuantity(1);
    setBidFace(2);
    setRoundOutcome(null);
    setHistory([]);
    setGestureOffset(0);
    setGestureActive(false);
    setMessage("骰盅正在摇动，结果由真实物理碰撞产生…");
    setPhase(PHASES.rolling);
    setRoundId((value) => value + 1);
    playDiceSound("roll", 0.55);
    playDiceSound("cup", 0.42);
    vibrate([45, 35, 60]);
  }, []);

  useEffect(() => {
    startRoundRef.current = startRound;
  }, [startRound]);

  useEffect(() => {
    if (!motionEnabled) {
      setDeviceTilt({ beta: 0, gamma: 0 });
      return undefined;
    }

    let lastMagnitude = 9.8;
    let lastShakeAt = 0;
    const handleOrientation = (event) => {
      setDeviceTilt({
        beta: Number.isFinite(event.beta) ? event.beta : 0,
        gamma: Number.isFinite(event.gamma) ? event.gamma : 0,
      });
    };
    const handleMotion = (event) => {
      const acceleration = event.accelerationIncludingGravity || event.acceleration;
      if (!acceleration) {
        return;
      }
      const magnitude = Math.sqrt(
        (acceleration.x || 0) ** 2 +
          (acceleration.y || 0) ** 2 +
          (acceleration.z || 0) ** 2,
      );
      const now = Date.now();
      const canShake =
        phaseRef.current === PHASES.ready || phaseRef.current === PHASES.finished;
      if (canShake && Math.abs(magnitude - lastMagnitude) > 11.5 && now - lastShakeAt > 1400) {
        lastShakeAt = now;
        startRoundRef.current?.();
      }
      lastMagnitude = magnitude;
    };

    window.addEventListener("deviceorientation", handleOrientation, true);
    window.addEventListener("devicemotion", handleMotion, true);
    return () => {
      window.removeEventListener("deviceorientation", handleOrientation, true);
      window.removeEventListener("devicemotion", handleMotion, true);
    };
  }, [motionEnabled]);

  const requestMotionControl = useCallback(async () => {
    try {
      const orientationClass = window.DeviceOrientationEvent;
      const motionClass = window.DeviceMotionEvent;
      const orientationPermission =
        typeof orientationClass?.requestPermission === "function"
          ? await orientationClass.requestPermission()
          : "granted";
      const motionPermission =
        typeof motionClass?.requestPermission === "function"
          ? await motionClass.requestPermission()
          : "granted";
      if (orientationPermission !== "granted" || motionPermission !== "granted") {
        setMessage("没有获得体感权限，仍可以点击或手势摇骰");
        return;
      }
      setMotionEnabled(true);
      setMessage("体感已开启：倾斜手机看桌面，快速晃动即可摇骰");
      vibrate(25);
    } catch {
      setMessage("当前浏览器暂不支持体感控制");
    }
  }, []);

  const handleGestureStart = useCallback((event) => {
    if (phaseRef.current !== PHASES.ready && phaseRef.current !== PHASES.finished) {
      return;
    }
    gestureRef.current = {
      x: event.clientX,
      y: event.clientY,
      time: performance.now(),
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setGestureActive(true);
  }, []);

  const handleGestureMove = useCallback((event) => {
    if (!gestureRef.current) {
      return;
    }
    const distanceX = event.clientX - gestureRef.current.x;
    setGestureOffset(Math.max(-1, Math.min(1, distanceX / 105)));
  }, []);

  const finishGesture = useCallback((event, cancelled = false) => {
    const gesture = gestureRef.current;
    gestureRef.current = null;
    setGestureActive(false);
    setGestureOffset(0);
    if (!gesture || cancelled) {
      return;
    }
    const distanceX = event.clientX - gesture.x;
    const distanceY = event.clientY - gesture.y;
    const duration = Math.max(80, performance.now() - gesture.time);
    const horizontalSpeed = Math.abs(distanceX) / duration;
    if (Math.abs(distanceX) >= 68 && Math.abs(distanceX) > Math.abs(distanceY) && horizontalSpeed > 0.22) {
      startRoundRef.current?.();
    } else {
      setMessage("再用力左右摇一下，或者点击开始按钮");
    }
  }, []);

  const handlePlayerSettled = useCallback(
    (playerId, values) => {
      settledRef.current = { ...settledRef.current, [playerId]: values };
      if (Object.keys(settledRef.current).length === players.length) {
        setResultsByPlayer(settledRef.current);
        setPhase(PHASES.bidding);
        setMessage("只看自己的骰子，轮到你先叫");
        addHistory("本局骰子已经全部自然停稳");
        vibrate(30);
      }
    },
    [addHistory, players.length],
  );

  const finishChallenge = useCallback(
    (challengerId, bid = currentBid) => {
      const outcome = resolveChallenge({
        bid,
        challengerId,
        resultsByPlayer: settledRef.current,
      });
      if (!outcome) {
        return;
      }
      const challenger = players.find((player) => player.id === challengerId);
      const bidder = players.find((player) => player.id === bid.bidderId);
      const loser = players.find((player) => player.id === outcome.loserId);
      setRoundOutcome(outcome);
      setPhase(PHASES.finished);
      setMessage(
        `${challenger.name}开了${bidder.name}：实际有${outcome.actualCount}个${bid.face}，${loser.name}输了`,
      );
      addHistory(
        `${challenger.name}选择开盅，实际${outcome.actualCount}个${bid.face}`,
      );
      vibrate([70, 40, 90]);
    },
    [addHistory, currentBid, players],
  );

  useEffect(() => {
    if (
      phase !== PHASES.bidding ||
      !currentPlayer ||
      currentPlayer.isHuman
    ) {
      return undefined;
    }

    setMessage(`${currentPlayer.name}正在看自己的骰子…`);
    aiTimerRef.current = window.setTimeout(() => {
      const action = chooseAiAction({
        currentBid,
        ownDice: resultsByPlayer[currentPlayer.id],
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
      const suggestedBid = getNextLegalBid(
        nextBid,
        nextBid.quantity,
        nextBid.face + 1,
        maxBidQuantity,
      );
      setCurrentPlayerId(nextPlayer.id);
      setBidQuantity(suggestedBid?.quantity ?? nextBid.quantity);
      setBidFace(suggestedBid?.face ?? nextBid.face);
      setMessage(nextPlayer.isHuman ? "轮到你：加数量、加点数，或者开" : `${nextPlayer.name}准备叫骰`);
    }, 760 + Math.random() * 420);

    return () => window.clearTimeout(aiTimerRef.current);
  }, [
    addHistory,
    currentBid,
    currentPlayer,
    finishChallenge,
    phase,
    players,
    resultsByPlayer,
    maxBidQuantity,
  ]);

  const submitBid = useCallback(() => {
    const proposedBid = { quantity: bidQuantity, face: bidFace, bidderId: "me" };
    if (!isHigherBid(currentBid, proposedBid)) {
      setMessage(`叫法必须高于 ${formatBid(currentBid)}`);
      vibrate(25);
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

  const updatePlayerCount = useCallback((event) => {
    const count = Number(event.target.value);
    setPlayerCount(count);
    setRoundId(0);
    setPhase(PHASES.ready);
    setCurrentBid(null);
    setResultsByPlayer({});
    setRoundOutcome(null);
    setMessage("人数已调整，开始一局新游戏吧");
  }, []);

  const currentBidder = currentBid
    ? players.find((player) => player.id === currentBid.bidderId)
    : null;

  return (
    <main className={`dice-game-page ${isWeappEmbed ? "dice-game-embedded" : ""}`}>
      <header className="dice-game-heading">
        <div>
          <span className="dice-kicker">BAR DICE · 单机模式 · v1.0.8</span>
          <h1>大话骰 · 吹牛</h1>
          <p>听骰子碰撞，再决定要不要相信对方。</p>
        </div>
        {!isWeappEmbed && <Link to="/" className="dice-back-link">返回点菜</Link>}
      </header>

      <section className="dice-status-strip">
        <div>
          <span>当前玩家</span>
          <strong>{phase === PHASES.rolling ? "摇骰中" : currentPlayer.name}</strong>
        </div>
        <div className="dice-current-bid">
          <span>当前叫法</span>
          <strong>{formatBid(currentBid)}</strong>
          {currentBidder && <small>来自 {currentBidder.name}</small>}
        </div>
        <label>
          玩家人数
          <select
            value={playerCount}
            onChange={updatePlayerCount}
            disabled={phase === PHASES.rolling || phase === PHASES.bidding}
          >
            {Array.from(
              { length: MAX_PLAYERS - MIN_PLAYERS + 1 },
              (_, index) => MIN_PLAYERS + index,
            ).map((count) => (
              <option key={count} value={count}>{count} 人</option>
            ))}
          </select>
        </label>
      </section>

      <section className="dice-scene-card">
        <DiceScene
          players={players}
          roundId={roundId}
          rolling={phase === PHASES.rolling}
          onPlayerSettled={handlePlayerSettled}
          deviceTilt={deviceTilt}
          gestureOffset={gestureOffset}
          gestureActive={gestureActive}
          onGestureStart={handleGestureStart}
          onGestureMove={handleGestureMove}
          onGestureEnd={(event) => finishGesture(event)}
          onGestureCancel={(event) => finishGesture(event, true)}
        />
        <div className="dice-scene-message">{message}</div>
        <div className="dice-scene-tools">
          <button
            type="button"
            className={`dice-motion-toggle ${motionEnabled ? "active" : ""}`}
            onClick={motionEnabled ? () => setMotionEnabled(false) : requestMotionControl}
            aria-label={motionEnabled ? "关闭体感" : "开启体感"}
          >
            ◉ {motionEnabled ? "体感开" : "开体感"}
          </button>
          <button
            type="button"
            className={`dice-sound-toggle ${soundEnabled ? "active" : ""}`}
            onClick={() => setSoundEnabled((value) => !value)}
            aria-label={soundEnabled ? "关闭音效" : "打开音效"}
          >
            {soundEnabled ? "♪" : "×"} 音效
          </button>
        </div>
        {(phase === PHASES.ready || phase === PHASES.finished) && (
          <div className="dice-gesture-hint">↔ 按住桌面左右摇，也可以晃动手机</div>
        )}
      </section>

      <section className="dice-private-card">
        <div>
          <span className="dice-kicker">PRIVATE DICE</span>
          <h2>我的骰子</h2>
        </div>
        <DiceValueRow values={resultsByPlayer.me} />
        {phase === PHASES.bidding && <small>只有你能看到这一组</small>}
      </section>

      <section className="dice-control-card">
        {(phase === PHASES.ready || phase === PHASES.finished) && (
          <button type="button" className="dice-primary-action" onClick={startRound}>
            {phase === PHASES.finished ? "再来一局" : "开始摇骰"}
          </button>
        )}

        {phase === PHASES.rolling && (
          <button type="button" className="dice-primary-action" disabled>
            物理碰撞中…
          </button>
        )}

        {phase === PHASES.bidding && currentPlayer.isHuman && (
          <>
            <div className="dice-bid-controls">
              <label>
                数量
                <div className="dice-stepper">
                  <button
                    type="button"
                    onClick={() => setBidQuantity((value) => Math.max(1, value - 1))}
                  >
                    −
                  </button>
                  <strong>{bidQuantity}</strong>
                  <button
                    type="button"
                    onClick={() =>
                      setBidQuantity((value) => Math.min(maxBidQuantity, value + 1))
                    }
                  >
                    +
                  </button>
                </div>
              </label>
              <div className="dice-face-picker">
                <span>点数</span>
                <div>
                  {[1, 2, 3, 4, 5, 6].map((face) => (
                    <button
                      key={face}
                      type="button"
                      className={bidFace === face ? "active" : ""}
                      onClick={() => setBidFace(face)}
                    >
                      {face}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="dice-action-row">
              <button type="button" className="dice-primary-action" onClick={submitBid}>
                叫骰 · {bidQuantity}个{bidFace}
              </button>
              <button
                type="button"
                className="dice-open-action"
                disabled={!currentBid}
                onClick={() => finishChallenge("me")}
              >
                开
              </button>
            </div>
          </>
        )}

        {phase === PHASES.bidding && !currentPlayer.isHuman && (
          <div className="dice-ai-thinking">
            <span />
            <span />
            <span />
            {currentPlayer.name} 正在思考
          </div>
        )}
      </section>

      {roundOutcome && (
        <section className="dice-reveal-card">
          <span className="dice-kicker">OPEN THE CUP</span>
          <h2>全桌开盅</h2>
          <p>{message}</p>
          <div className="dice-player-results">
            {players.map((player) => (
              <div key={player.id} className={roundOutcome.loserId === player.id ? "loser" : ""}>
                <strong>{player.name}</strong>
                <DiceValueRow values={resultsByPlayer[player.id]} />
                {roundOutcome.loserId === player.id && <em>本局输家</em>}
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="dice-rules-card">
        <div>
          <span className="dice-kicker">HOW TO PLAY</span>
          <h2>这一桌怎么玩</h2>
        </div>
        <ol>
          <li>每人 5 颗骰子，只能看到自己的点数。</li>
          <li>叫“3个5”表示全桌至少有 3 颗五；下一位必须加数量或点数。</li>
          <li>1 点通常作万能点；叫 1 时只统计真正的 1。</li>
          <li>不相信上一位就点“开”，数量不足时上一位输，否则开盅的人输。</li>
        </ol>
        {history.length > 0 && (
          <div className="dice-history">
            {history.map((entry, index) => <p key={`${entry}-${index}`}>{entry}</p>)}
          </div>
        )}
      </section>
    </main>
  );
}
