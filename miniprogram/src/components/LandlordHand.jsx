import { ScrollView, View } from "@tarojs/components";

import LandlordCard from "./LandlordCard";
import "./LandlordHand.css";

/** Horizontal hand with controlled multi-card selection. */
export default function LandlordHand({ cards = [], selected = [], disabled = false, onToggle }) {
  return (
    <ScrollView scrollX enhanced showScrollbar={false} className="ll-hand-scroll">
      <View className={`ll-hand ${disabled ? "disabled" : ""}`}>
        {cards.map((card) => <LandlordCard key={card.id} card={card} selected={selected.includes(card.id)} onClick={() => !disabled && onToggle?.(card.id)} />)}
      </View>
    </ScrollView>
  );
}
