import { Text, View } from "@tarojs/components";

import ChessPiece from "./ChessPiece";
import "./ChessBoard.css";

/**
 * Draw a 9 x 10 Chinese-chess board on line intersections.
 *
 * The engine stores canonical coordinates with black at y=0 and red at y=9.
 * Only display coordinates are flipped for a black viewer; taps are converted
 * back to the canonical server coordinates.
 */
export default function ChessBoard({ pieces = [], myColor = "red", selectedId = "", lastMove, pendingMove, disabled, onCell }) {
  const flipped = myColor === "black";
  const points = [];
  for (let displayY = 0; displayY < 10; displayY += 1) {
    for (let displayX = 0; displayX < 9; displayX += 1) {
      const x = flipped ? 8 - displayX : displayX;
      const y = flipped ? 9 - displayY : displayY;
      const currentPiece = pieces.find((item) => item.alive && item.x === x && item.y === y);
      const isMovingSource = currentPiece?.id === pendingMove?.pieceId;
      const isMovingTarget = pendingMove?.x === x && pendingMove?.y === y;
      const piece = isMovingSource ? null : currentPiece;
      points.push(
        <View
          key={`${x}-${y}`}
          className="chess-point"
          data-board-x={x}
          data-board-y={y}
          style={{ left: `${displayX * 12.5}%`, top: `${displayY * (100 / 9)}%` }}
          onClick={() => !disabled && onCell(piece, x, y)}
        >
          {piece && <ChessPiece piece={piece} selected={selectedId === piece.id} lastMoved={lastMove?.piece_id === piece.id} />}
          {isMovingTarget && <View className={`chess-pending-piece ${pendingMove.color || "red"}`}><Text>{pendingMove.label || "子"}</Text></View>}
        </View>
      );
    }
  }
  return (
    <View className={`chess-board ${disabled ? "disabled" : ""}`}>
      <View className="chess-board-surface">
        <View className="chess-lines">
          {Array.from({ length: 10 }, (_, index) => <View key={`h-${index}`} className="chess-line horizontal" style={{ top: `${index * (100 / 9)}%` }} />)}
          {Array.from({ length: 9 }, (_, index) => (
            <View key={`v-${index}`} className={`chess-file col-${index}`} style={{ left: `${index * 12.5}%` }}>
              {index === 0 || index === 8 ? (
                <View className="chess-line vertical full" />
              ) : (
                <><View className="chess-line vertical top" /><View className="chess-line vertical bottom" /></>
              )}
            </View>
          ))}
          <View className="chess-river"><Text>楚 河</Text><Text>漢 界</Text></View>
          <View className="chess-palace top first" /><View className="chess-palace top second" />
          <View className="chess-palace bottom first" /><View className="chess-palace bottom second" />
        </View>
        <View className="chess-points">{points}</View>
      </View>
    </View>
  );
}
