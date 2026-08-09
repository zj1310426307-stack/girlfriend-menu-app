import { Text, View } from "@tarojs/components";

import "./AnimalPiece.css";

/** One tactile animal token with side color and selected state. */
export default function AnimalPiece({ piece, selected = false }) {
  if (!piece?.alive) return null;
  return <View className={`animal-piece ${piece.color} ${selected ? "selected" : ""}`}><Text>{piece.label}</Text></View>;
}
