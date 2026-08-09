import { Text, View } from "@tarojs/components";

import "./LandlordCard.css";

const SUIT = { spade: "♠", heart: "♥", club: "♣", diamond: "♦", joker: "★" };

/** Compact tactile card used by the hand and table components. */
export default function LandlordCard({ card, selected = false, compact = false, onClick }) {
  if (!card) return null;
  const joker = card.rank === "SJ" || card.rank === "BJ";
  return (
    <View
      className={`ll-card ${card.color === "red" ? "red" : "black"} ${selected ? "selected" : ""} ${compact ? "compact" : ""}`}
      data-card-id={card.id}
      onClick={() => onClick?.(card)}
    >
      <Text>{joker ? (card.rank === "BJ" ? "大王" : "小王") : card.rank}</Text>
      <Text>{SUIT[card.suit] || ""}</Text>
      <Text>{joker ? "JOKER" : SUIT[card.suit]}</Text>
    </View>
  );
}
