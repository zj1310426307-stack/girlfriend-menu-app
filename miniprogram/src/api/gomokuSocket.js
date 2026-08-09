import { connectGameRoom } from "./gameSocket";

/** Five-in-a-row uses the shared game-room envelope and transport. */
export function connectGomokuRoom(options) {
  return connectGameRoom({
    ...options,
    gameType: "gomoku"
  });
}
