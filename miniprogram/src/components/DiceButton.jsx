import { Text, View } from "@tarojs/components";

import "./DiceButton.css";

const DOTS = {
  1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8]
};

export default function DiceButton({ value, disabled, loading, onClick }) {
  return (
    <View className={`flight-dice-button ${disabled ? "disabled" : ""} ${loading ? "rolling" : ""}`} onClick={() => !disabled && onClick?.()}>
      <View className="flight-die">
        {Array.from({ length: 9 }, (_, index) => <View key={index} className={(DOTS[value] || []).includes(index) ? "dot" : ""} />)}
      </View>
      <View><Text>{loading ? "骰子飞行中…" : value ? `${value} 点` : "掷骰子"}</Text><Text>{disabled ? "等待当前步骤完成" : "点数由服务器生成"}</Text></View>
    </View>
  );
}
