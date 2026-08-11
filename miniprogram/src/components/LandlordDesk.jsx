import { Text, View } from "@tarojs/components";

import LandlordCard from "./LandlordCard";
import "./LandlordDesk.css";

const COMBO_LABELS = {
  single: "单张", pair: "对子", triple: "三张", triple_single: "三带一",
  triple_pair: "三带一对", straight: "顺子", pair_straight: "连对",
  airplane: "飞机", airplane_single: "飞机带单", airplane_pair: "飞机带对",
  four_two_single: "四带二", four_two_pair: "四带两对", bomb: "炸弹", rocket: "王炸"
};

/** Center table showing the current legal play and its owner. */
export default function LandlordDesk({ play, name = "" }) {
  return (
    <View className="ll-desk">
      {play ? (
        <>
          <Text>{name || "对方"} · {COMBO_LABELS[play.combo?.type] || "出牌"}</Text>
          <View>{play.cards?.map((card) => <LandlordCard key={card.id} card={card} compact />)}</View>
        </>
      ) : <Text>等待本轮第一手牌</Text>}
    </View>
  );
}
