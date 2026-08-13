import { useEffect, useState } from "react";
import { Text, View } from "@tarojs/components";

import "./DiceButton.css";

const DOTS = {
  1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8]
};

/** Show a server-authoritative die with immediate non-authoritative motion. */
export default function DiceButton({ value, disabled, loading, onClick }) {
  const [rollingFace, setRollingFace] = useState(1);

  // Give immediate visual feedback while the authoritative result is produced
  // by the server. The preview face is never used as the game result.
  useEffect(() => {
    if (!loading) return undefined;
    let nextFace = 1;
    const timer = setInterval(() => {
      nextFace = nextFace % 6 + 1;
      setRollingFace(nextFace);
    }, 70);
    return () => clearInterval(timer);
  }, [loading]);

  const displayedValue = loading ? rollingFace : value;
  return (
    <View className={`flight-dice-button ${disabled ? "disabled" : ""} ${loading ? "rolling" : ""}`} onClick={() => !disabled && onClick?.()}>
      <View className="flight-die">
        {Array.from({ length: 9 }, (_, index) => <View key={index} className={(DOTS[displayedValue] || []).includes(index) ? "dot" : ""} />)}
      </View>
      <View><Text>{loading ? "正在掷骰…" : value ? `${value} 点` : "掷骰子"}</Text><Text>{loading ? "结果马上揭晓" : disabled ? "等待当前步骤完成" : "点数由服务器生成"}</Text></View>
    </View>
  );
}
