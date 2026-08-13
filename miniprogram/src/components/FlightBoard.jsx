import { Text, View } from "@tarojs/components";

import "./FlightBoard.css";

const TRACK_SIZE = 28;
const START_OFFSETS = [0, 14];
const EVENT_MARKS = { 4: "♥", 8: "餐", 12: "乐", 16: "挑", 20: "♥", 24: "餐" };
const EVENT_NAMES = { 4: "爱心", 8: "厨房", 12: "欢乐", 16: "挑战", 20: "爱心", 24: "美食" };

/** Normalize persisted and API player identifiers for board rendering. */
function playerId(player) {
  return player?.id || player?.player_id;
}

/** Convert one player's local track coordinate into the shared ring. */
function globalPosition(localPosition, playerIndex) {
  if (localPosition < 0 || localPosition >= TRACK_SIZE) return null;
  return (localPosition + START_OFFSETS[playerIndex]) % TRACK_SIZE;
}

/** Place the 28 server track squares on a compact rounded flight path. */
function trackStyle(index) {
  const angle = -Math.PI / 2 + (index / TRACK_SIZE) * Math.PI * 2;
  const wave = index % 7 === 0 ? 3 : index % 7 === 3 ? -2 : 0;
  const x = 50 + (42 + wave) * Math.cos(angle);
  const y = 49 + (39 - wave) * Math.sin(angle);
  return { left: `${x}%`, top: `${y}%` };
}

/** Render the authoritative flight state without inventing client-side moves. */
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
        <View className="flight-sky-line one" /><View className="flight-sky-line two" />
        {Array.from({ length: TRACK_SIZE }, (_, index) => {
          const tokens = tokensByTrack.get(index) || [];
          const event = EVENT_MARKS[index];
          return (
            <View
              key={index}
              className={`flight-track-node tone-${index % 4} ${event ? "event" : ""} ${index === 0 || index === 14 ? "start" : ""}`}
              style={trackStyle(index)}
            >
              <Text>{event || (index === 0 || index === 14 ? "起" : index + 1)}</Text>
              {event && <Text className="flight-event-name">{EVENT_NAMES[index]}</Text>}
              <View className="flight-cell-tokens">{tokens.map(renderToken)}</View>
            </View>
          );
        })}
        <View className="flight-board-center">
          <Text>COUPLE FLIGHT</Text>
          <Text>{state.dice || "✈"}</Text>
          <Text>{state.dice ? `本轮 ${state.dice} 点` : "绕行 · 互动 · 冲向终点"}</Text>
        </View>
        <View className="flight-shortcut"><Text>云端捷径</Text><Text>→</Text></View>
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
