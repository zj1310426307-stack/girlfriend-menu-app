import { Text, View } from "@tarojs/components";

import "./GomokuBoard.css";

const BOARD_SIZE = 15;
const POINTS = Array.from({ length: BOARD_SIZE * BOARD_SIZE }, (_, index) => ({
  x: index % BOARD_SIZE,
  y: Math.floor(index / BOARD_SIZE)
}));

function normalizeStone(value) {
  if (value === 1 || value === "black" || value === "BLACK") return "black";
  if (value === 2 || value === "white" || value === "WHITE") return "white";
  return "";
}

function isLastMove(lastMove, x, y) {
  if (!lastMove) return false;
  if (Array.isArray(lastMove)) return lastMove[0] === x && lastMove[1] === y;
  return Number(lastMove.x) === x && Number(lastMove.y) === y;
}

/** A 15x15 touch-friendly board. The server remains authoritative for every move. */
export default function GomokuBoard({
  board = [],
  lastMove,
  disabled = false,
  onMove
}) {
  return (
    <View className={`gomoku-board ${disabled ? "disabled" : ""}`}>
      <View className="gomoku-grid">
        {POINTS.map(({ x, y }) => {
          const stone = normalizeStone(board?.[y]?.[x]);
          const edgeClasses = [
            y === 0 ? "top" : "",
            y === BOARD_SIZE - 1 ? "bottom" : "",
            x === 0 ? "left" : "",
            x === BOARD_SIZE - 1 ? "right" : ""
          ].filter(Boolean).join(" ");
          return (
            <View
              key={`${x}-${y}`}
              className={`gomoku-point ${edgeClasses}`}
              data-x={x}
              data-y={y}
              onClick={() => !disabled && !stone && onMove?.(x, y)}
            >
              {stone && (
                <View className={`gomoku-stone ${stone} ${isLastMove(lastMove, x, y) ? "last" : ""}`}>
                  {isLastMove(lastMove, x, y) && <Text />}
                </View>
              )}
              {((x === 3 || x === 7 || x === 11) && (y === 3 || y === 7 || y === 11)) && !stone && (
                <View className="gomoku-star" />
              )}
            </View>
          );
        })}
      </View>
    </View>
  );
}
