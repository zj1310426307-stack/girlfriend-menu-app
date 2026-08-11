import { useEffect, useRef, useState } from "react";
import Taro from "@tarojs/taro";
import { Canvas, Input, Switch, Text, View } from "@tarojs/components";

import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const STORAGE_KEY = "gf_wheel_items";
const HISTORY_KEY = "gf_wheel_history";
const NO_REPEAT_KEY = "gf_wheel_no_repeat";
const MIN_ITEMS = 2;
const MAX_ITEMS = 12;
const DEFAULT_ITEMS = ["吃火锅", "看电影", "喝奶茶", "去散步", "早点睡", "再转一次"];
const COLORS = [
  "#f48ca0", "#ffd8cd", "#90bfe4", "#f6bd60", "#a7d7c5", "#cdb7ee",
  "#f6a6bf", "#ffe7a3", "#8ed1d2", "#f2b6a0", "#aebee9", "#d9c2a7"
];

function readItems() {
  try {
    const saved = Taro.getStorageSync(STORAGE_KEY);
    if (Array.isArray(saved) && saved.length >= MIN_ITEMS) return saved.slice(0, MAX_ITEMS);
  } catch (error) {
    console.warn("读取转盘选项失败", error);
  }
  return DEFAULT_ITEMS;
}

function readHistory() {
  try {
    const saved = Taro.getStorageSync(HISTORY_KEY);
    return Array.isArray(saved) ? saved.slice(0, 6) : [];
  } catch (_) {
    return [];
  }
}

function readNoRepeat() {
  try {
    return Taro.getStorageSync(NO_REPEAT_KEY) !== false;
  } catch (_) {
    return true;
  }
}

function shortLabel(value, index) {
  const label = String(value || "").trim() || `选项${index + 1}`;
  return label.length > 7 ? `${label.slice(0, 7)}…` : label;
}

export default function WheelPage() {
  const [allowed, setAllowed] = useState(false);
  const [items, setItems] = useState(readItems);
  const [ready, setReady] = useState(false);
  const [spinning, setSpinning] = useState(false);
  const [winner, setWinner] = useState("");
  const [history, setHistory] = useState(readHistory);
  const [noRepeat, setNoRepeat] = useState(readNoRepeat);
  const canvasRef = useRef(null);
  const contextRef = useRef(null);
  const sizeRef = useRef(0);
  const rotationRef = useRef(0);
  const animationRef = useRef(null);

  useEffect(() => {
    setAllowed(ensureInvitePassed());
    return () => {
      if (animationRef.current) clearTimeout(animationRef.current);
    };
  }, []);

  useEffect(() => {
    if (!allowed) return undefined;
    let cancelled = false;
    let retryTimer;
    const initialize = (attempt = 0) => {
      Taro.createSelectorQuery()
        .select("#decision-wheel")
        .fields({ node: true, size: true })
        .exec((result) => {
          if (cancelled) return;
          const info = result?.[0];
          if ((!info?.node || !info?.width) && attempt < 6) {
            retryTimer = setTimeout(() => initialize(attempt + 1), 180);
            return;
          }
          if (!info?.node) return;
          const dpr = Math.min(2, Taro.getWindowInfo().pixelRatio || 1);
          const size = Math.max(280, Math.min(info.width, info.height || info.width));
          info.node.width = size * dpr;
          info.node.height = size * dpr;
          const context = info.node.getContext("2d");
          context.scale(dpr, dpr);
          canvasRef.current = info.node;
          contextRef.current = context;
          sizeRef.current = size;
          setReady(true);
        });
    };
    Taro.nextTick(() => initialize());
    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
    };
  }, [allowed]);

  const drawWheel = (rotation = rotationRef.current) => {
    const context = contextRef.current;
    const size = sizeRef.current;
    if (!context || !size) return;
    const center = size / 2;
    const radius = center - 8;
    const segment = (Math.PI * 2) / items.length;
    context.clearRect(0, 0, size, size);
    context.save();
    context.translate(center, center);

    items.forEach((item, index) => {
      const start = rotation - Math.PI / 2 + index * segment;
      const end = start + segment;
      context.beginPath();
      context.moveTo(0, 0);
      context.arc(0, 0, radius, start, end);
      context.closePath();
      context.fillStyle = COLORS[index % COLORS.length];
      context.fill();
      context.strokeStyle = "rgba(255,255,255,.82)";
      context.lineWidth = 2;
      context.stroke();

      context.save();
      context.rotate(start + segment / 2);
      context.fillStyle = index % 3 === 1 ? "#654b47" : "#ffffff";
      context.font = `700 ${items.length > 9 ? 11 : items.length > 6 ? 13 : 15}px sans-serif`;
      context.textAlign = "right";
      context.textBaseline = "middle";
      context.shadowColor = "rgba(60,35,35,.16)";
      context.shadowBlur = 2;
      context.fillText(shortLabel(item, index), radius - 24, 0);
      context.restore();
    });

    context.beginPath();
    context.arc(0, 0, 37, 0, Math.PI * 2);
    const centerGradient = context.createRadialGradient(-8, -10, 3, 0, 0, 38);
    centerGradient.addColorStop(0, "#fffdfb");
    centerGradient.addColorStop(1, "#e4617b");
    context.fillStyle = centerGradient;
    context.fill();
    context.strokeStyle = "rgba(255,255,255,.9)";
    context.lineWidth = 4;
    context.stroke();
    context.fillStyle = "#fff";
    context.font = "800 15px sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText("GO", 0, 1);
    context.restore();
  };

  useEffect(() => {
    if (!ready) return;
    drawWheel();
  }, [items, ready]);

  useEffect(() => {
    try {
      Taro.setStorageSync(STORAGE_KEY, items);
    } catch (error) {
      console.warn("保存转盘选项失败", error);
    }
  }, [items]);

  useEffect(() => {
    try {
      Taro.setStorageSync(HISTORY_KEY, history);
      Taro.setStorageSync(NO_REPEAT_KEY, noRepeat);
    } catch (error) {
      console.warn("保存转盘偏好失败", error);
    }
  }, [history, noRepeat]);

  const spin = () => {
    if (!ready || spinning) return;
    const candidates = items
      .map((_, index) => index)
      .filter((index) => !noRepeat || items.length < 2 || items[index] !== history[0]);
    const pool = candidates.length ? candidates : items.map((_, index) => index);
    const winnerIndex = pool[Math.floor(Math.random() * pool.length)];
    const segment = (Math.PI * 2) / items.length;
    const current = ((rotationRef.current % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
    const target = ((-(winnerIndex + 0.5) * segment) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
    const distance = Math.PI * 2 * (5 + Math.floor(Math.random() * 3))
      + ((target - current + Math.PI * 2) % (Math.PI * 2));
    const from = rotationRef.current;
    const duration = 3600;
    const startedAt = Date.now();
    setWinner("");
    setSpinning(true);
    Taro.vibrateShort({ type: "light" }).catch(() => {});

    const frame = () => {
      const progress = Math.min(1, (Date.now() - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 5);
      rotationRef.current = from + distance * eased;
      drawWheel(rotationRef.current);
      if (progress < 1) {
        const canvas = canvasRef.current;
        animationRef.current = canvas?.requestAnimationFrame
          ? canvas.requestAnimationFrame(frame)
          : setTimeout(frame, 16);
        return;
      }
      rotationRef.current = target;
      drawWheel(target);
      const result = String(items[winnerIndex] || `选项${winnerIndex + 1}`).trim();
      setWinner(result);
      setHistory((current) => [result, ...current].slice(0, 6));
      setSpinning(false);
      Taro.vibrateShort({ type: "medium" }).catch(() => {});
    };
    frame();
  };

  const updateItem = (index, value) => {
    if (spinning) return;
    setItems((current) => current.map((item, itemIndex) => itemIndex === index ? value : item));
    setWinner("");
  };

  const addItem = () => {
    if (spinning || items.length >= MAX_ITEMS) return;
    setItems((current) => [...current, `选项${current.length + 1}`]);
    setWinner("");
  };

  const removeItem = (index) => {
    if (spinning || items.length <= MIN_ITEMS) return;
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
    setWinner("");
  };

  if (!allowed) return <View className="wheel-loading"><Text>正在返回邀请码页面…</Text></View>;

  return (
    <View className="wheel-page">
      <View className="wheel-hero">
        <Text className="wheel-kicker">MAKE A SWEET CHOICE</Text>
        <Text className="wheel-title">今晚听转盘的</Text>
        <Text className="wheel-desc">纠结吃什么、去哪里、谁先行动，都交给好运决定。</Text>
      </View>

      <View className="wheel-stage">
        <View className="wheel-pointer" />
        <Canvas id="decision-wheel" canvasId="decision-wheel" type="2d" className="wheel-canvas" />
        {!ready && <View className="wheel-overlay"><Text>正在布置转盘…</Text></View>}
      </View>

      <View className={`wheel-spin ${spinning ? "disabled" : ""}`} onClick={spin}>
        <Text>{spinning ? "好运正在转动…" : "转一下"}</Text>
      </View>

      {winner && (
        <View className="wheel-result">
          <Text>今晚就选</Text>
          <Text>{winner}</Text>
        </View>
      )}

      <View className="wheel-fairness">
        <View><Text>连续两次不重复</Text><Text>开启后自动避开上一次结果</Text></View>
        <Switch checked={noRepeat} color="#d85f77" disabled={spinning} onChange={(event) => setNoRepeat(event.detail.value)} />
      </View>

      {history.length > 0 && (
        <View className="wheel-history">
          <View><Text>最近结果</Text><Text onClick={() => setHistory([])}>清空</Text></View>
          <View>{history.map((item, index) => <Text key={`${item}-${index}`}>{index + 1}. {item}</Text>)}</View>
        </View>
      )}

      <View className="wheel-editor">
        <View className="wheel-editor-head">
          <View>
            <Text>转盘内容</Text>
            <Text>{items.length} 个分区 · 自动保存在本机</Text>
          </View>
          <View className={`wheel-add ${items.length >= MAX_ITEMS ? "disabled" : ""}`} onClick={addItem}>
            <Text>＋ 添加</Text>
          </View>
        </View>
        <View className="wheel-options">
          {items.map((item, index) => (
            <View className="wheel-option" key={`wheel-${index}`}>
              <View className="wheel-color" style={{ background: COLORS[index % COLORS.length] }} />
              <Text className="wheel-number">{index + 1}</Text>
              <Input
                value={item}
                maxlength={16}
                disabled={spinning}
                placeholder={`填写选项${index + 1}`}
                onInput={(event) => updateItem(index, event.detail.value)}
              />
              <View className={`wheel-remove ${items.length <= MIN_ITEMS ? "disabled" : ""}`} onClick={() => removeItem(index)}>
                <Text>删除</Text>
              </View>
            </View>
          ))}
        </View>
        <Text className="wheel-tip">至少 2 个、最多 12 个分区，每个选项被选中的机会相同。</Text>
      </View>
    </View>
  );
}
