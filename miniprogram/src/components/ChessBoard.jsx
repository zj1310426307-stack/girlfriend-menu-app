import { Text, View } from "@tarojs/components";

import ChessPiece from "./ChessPiece";
import "./ChessBoard.css";

/** Draw a responsive 9 x 10 board and normalize taps to server coordinates. */
export default function ChessBoard({ pieces = [], myColor = "red", selectedId = "", lastMove, disabled, onCell }) {
  const flipped = myColor === "black";
  const cells = [];
  for (let displayY = 0; displayY < 10; displayY += 1) {
    for (let displayX = 0; displayX < 9; displayX += 1) {
      const x = flipped ? 8 - displayX : displayX;
      const y = flipped ? 9 - displayY : displayY;
      const piece = pieces.find((item) => item.alive && item.x === x && item.y === y);
      cells.push(
        <View key={`${x}-${y}`} className={`chess-cell row-${displayY} col-${displayX}`} onClick={() => !disabled && onCell(piece, x, y)}>
          {piece && <ChessPiece piece={piece} selected={selectedId === piece.id} lastMoved={lastMove?.piece_id === piece.id} />}
        </View>
      );
    }
  }
  return (
    <View className={`chess-board ${disabled ? "disabled" : ""}`}>
      <View className="chess-river"><Text>楚 河</Text><Text>漢 界</Text></View>
      <View className="chess-palace top" /><View className="chess-palace bottom" />
      <View className="chess-grid">{cells}</View>
    </View>
  );
}
