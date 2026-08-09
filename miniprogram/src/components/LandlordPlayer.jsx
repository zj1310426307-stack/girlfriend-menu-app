import { Text, View } from "@tarojs/components";

import "./LandlordPlayer.css";

/** Avatar and hidden-card count for one table participant. */
export default function LandlordPlayer({ name, count = 0, active = false, landlord = false, ai = false }) {
  return (
    <View className={`ll-player ${active ? "active" : ""}`}>
      <View><Text>{ai ? "AI" : name?.slice(0, 1) || "玩"}</Text></View>
      <Text>{name || "等待加入"}{landlord ? " · 地主" : ""}</Text>
      <Text>{count} 张</Text>
    </View>
  );
}
