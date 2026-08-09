import { Text, View } from "@tarojs/components";

import LandlordCard from "./LandlordCard";
import "./LandlordDesk.css";

/** Center table showing the current legal play and its owner. */
export default function LandlordDesk({ play, name = "" }) {
  return (
    <View className="ll-desk">
      {play ? (
        <>
          <Text>{name || "对方"} · {play.combo?.type || "出牌"}</Text>
          <View>{play.cards?.map((card) => <LandlordCard key={card.id} card={card} compact />)}</View>
        </>
      ) : <Text>等待本轮第一手牌</Text>}
    </View>
  );
}
