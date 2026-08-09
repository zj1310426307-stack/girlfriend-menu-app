import { Text, View } from "@tarojs/components";

import AnimalPiece from "./AnimalPiece";
import "./AnimalBoard.css";

const RIVER = new Set(Array.from({ length: 12 }, (_, i) => `${i % 4 < 2 ? 1 + i % 2 : 4 + i % 2}-${3 + Math.floor(i / 4)}`));
const DENS = new Set(["3-0", "3-8"]);
const TRAPS = new Set(["2-0", "4-0", "3-1", "2-8", "4-8", "3-7"]);

/** Responsive 7x9 board; rules remain fully authoritative on the backend. */
export default function AnimalBoard({ pieces = [], selectedId, disabled = false, onCell }) {
  const cells = Array.from({ length: 63 }, (_, index) => ({ x: index % 7, y: Math.floor(index / 7) }));
  const living = new Map(pieces.filter((item) => item.alive).map((item) => [`${item.x}-${item.y}`, item]));
  return (
    <View className={`animal-board ${disabled ? "disabled" : ""}`}>
      {cells.map(({ x, y }) => {
        const key = `${x}-${y}`;
        const piece = living.get(key);
        const terrain = RIVER.has(key) ? "river" : DENS.has(key) ? "den" : TRAPS.has(key) ? "trap" : "land";
        return (
          <View key={key} className={`animal-cell ${terrain}`} data-x={x} data-y={y} onClick={() => !disabled && onCell?.(piece, x, y)}>
            {terrain === "den" && !piece && <Text>穴</Text>}
            {terrain === "trap" && !piece && <Text>陷</Text>}
            <AnimalPiece piece={piece} selected={piece?.id === selectedId} />
          </View>
        );
      })}
    </View>
  );
}
