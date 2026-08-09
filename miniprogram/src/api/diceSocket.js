import { connectGameRoom } from "./gameSocket";

export function connectDiceRoom({ roomCode, playerId, playerName, inviteCode, onState, onError, onStatus }) {
  return connectGameRoom({
    roomCode,
    gameType: "dice",
    playerId,
    playerName,
    inviteCode,
    onState,
    onError,
    onStatus
  });
}
