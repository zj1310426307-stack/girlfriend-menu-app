import { Text, View } from "@tarojs/components";

import "./ChessPiece.css";

/** Render one round Chinese-chess piece with color and selection semantics. */
export default function ChessPiece({ piece, selected, lastMoved }) {
  return (
    <View className={`chess-piece ${piece.color} ${selected ? "selected" : ""} ${lastMoved ? "last-moved" : ""}`}>
      <View><Text>{piece.label}</Text></View>
    </View>
  );
}
