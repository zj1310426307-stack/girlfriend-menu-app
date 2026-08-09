import { Text, View } from "@tarojs/components";

import "./FlightBoard.css";

const TRACK_SIZE = 28;
const START_OFFSETS = [0, 14];
const EVENT_MARKS = { 4: "♥", 8: "餐", 12: "乐", 16: "挑", 20: "♥", 24: "礼" };

function trackIndex(row, column) {
  if (row === 0) return column;
  if (column === 7) return 7 + row;
  if (row === 7) return 21 - column;
  if (column === 0) return 28 - row;
  return null;
}

function playerId(player) {
  return player?.id || player?.player_id;
}

function globalPosition(localPosition, playerIndex) {
  if (localPosition < 0 || localPosition >= TRACK_SIZE) return null;
  return (localPosition + START_OFFSETS[playerIndex]) % TRACK_SIZE;
}

export default function FlightBoard({ state, meId, onPiece }) {
  const players = state.players || [];
  const pieces = state.pieces || {};
  const movable = state.movable || [];
  const tokensByTrack = new Map();

  players.forEach((player, playerIndex) => {
    const id = playerId(player);
    (pieces[id] || []).forEach((position, pieceIndex) => {
      const global = globalPosition(position, playerIndex);
      if (global == null) return;
      const current = tokensByTrack.get(global) || [];
      current.push({ id, pieceIndex, color: player.color || (playerIndex ? "blue" : "red") });
      tokensByTrack.set(global, current);
    });
  });

  const renderToken = (token) => {
    const canMove = token.id === meId && movable.includes(token.pieceIndex);
    return (
      <View
        key={`${token.id}-${token.pieceIndex}`}
        className={`flight-token ${token.color} ${canMove ? "movable" : ""}`}
        onClick={(event) => {
          event?.stopPropagation?.();
          if (canMove) onPiece(token.pieceIndex);
        }}
      ><Text>{token.pieceIndex + 1}</Text></View>
    );
  };

  return (
    <View className="flight-board-shell">
      <View className="flight-board">
        {Array.from({ length: 64 }, (_, cellIndex) => {
          const row = Math.floor(cellIndex / 8);
          const column = cellIndex % 8;
          const index = trackIndex(row, column);
          const tokens = index == null ? [] : tokensByTrack.get(index) || [];
          return (
            <View key={cellIndex} className={`flight-cell ${index == null ? "inner" : "track"} ${EVENT_MARKS[index] ? "event" : ""}`}>
              {index != null && <Text className="flight-cell-index">{EVENT_MARKS[index] || index + 1}</Text>}
              <View className="flight-cell-tokens">{tokens.map(renderToken)}</View>
            </View>
          );
        })}
        <View className="flight-board-center">
          <Text>COUPLE</Text>
          <Text>{state.dice || "♥"}</Text>
          <Text>{state.dice ? `本轮 ${state.dice} 点` : "一起飞向终点"}</Text>
        </View>
      </View>

      <View className="flight-hangars">
        {players.map((player, playerIndex) => {
          const id = playerId(player);
          const color = player.color || (playerIndex ? "blue" : "red");
          const values = pieces[id] || [];
          return (
            <View key={id} className={`flight-hangar ${color}`}>
              <View className="flight-hangar-title"><Text>{player.name}</Text><Text>{values.filter((value) => value === 32).length}/4 到达</Text></View>
              <View className="flight-runway">
                {[28, 29, 30, 31].map((position) => (
                  <View key={position} className={position === 29 ? "event" : ""}>
                    {position === 29 && <Text>乐</Text>}
                    {values.map((value, pieceIndex) => value === position ? renderToken({ id, pieceIndex, color }) : null)}
                  </View>
                ))}
              </View>
              <View className="flight-home-pieces">
                {values.map((value, pieceIndex) => value === -1 ? renderToken({ id, pieceIndex, color }) : null)}
                {values.every((value) => value !== -1) && <Text>四架飞机都已出发</Text>}
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}
