export const DICE_PER_PLAYER = 5;
export const MIN_PLAYERS = 2;
export const MAX_PLAYERS = 6;

const AI_NAMES = ["玩家A", "玩家B", "玩家C", "玩家D", "玩家E"];

export function createPlayers(playerCount) {
  const safeCount = Math.min(MAX_PLAYERS, Math.max(MIN_PLAYERS, Number(playerCount) || 3));
  return [
    { id: "me", name: "我", isHuman: true },
    ...AI_NAMES.slice(0, safeCount - 1).map((name, index) => ({
      id: `ai-${index + 1}`,
      name,
      isHuman: false,
    })),
  ];
}

export function getNextPlayer(players, currentPlayerId) {
  const currentIndex = players.findIndex((player) => player.id === currentPlayerId);
  return players[(currentIndex + 1 + players.length) % players.length];
}

export function isHigherBid(currentBid, nextBid) {
  if (!nextBid || nextBid.quantity < 1 || nextBid.face < 1 || nextBid.face > 6) {
    return false;
  }
  if (!currentBid) return true;
  return (
    nextBid.quantity > currentBid.quantity ||
    (nextBid.quantity === currentBid.quantity && nextBid.face > currentBid.face)
  );
}

export function getNextLegalBid(currentBid, preferredQuantity, preferredFace, maxQuantity) {
  let quantity = Math.min(maxQuantity, Math.max(1, preferredQuantity));
  let face = Math.min(6, Math.max(1, preferredFace));

  if (!currentBid || isHigherBid(currentBid, { quantity, face })) {
    return { quantity, face };
  }
  if (currentBid.face < 6) {
    return { quantity: currentBid.quantity, face: currentBid.face + 1 };
  }
  quantity = currentBid.quantity + 1;
  return quantity <= maxQuantity ? { quantity, face: 1 } : null;
}

export function countMatchingDice(resultsByPlayer, face) {
  return Object.values(resultsByPlayer)
    .reduce((all, values) => all.concat(values || []), [])
    .filter((value) => value === face || (face !== 1 && value === 1)).length;
}

export function resolveChallenge({ bid, challengerId, resultsByPlayer }) {
  if (!bid) return null;
  const actualCount = countMatchingDice(resultsByPlayer, bid.face);
  const bidSucceeded = actualCount >= bid.quantity;
  return {
    actualCount,
    bidSucceeded,
    winnerId: bidSucceeded ? bid.bidderId : challengerId,
    loserId: bidSucceeded ? challengerId : bid.bidderId,
  };
}

export function formatBid(bid) {
  return bid ? `${bid.quantity}个${bid.face}` : "还没有人叫骰";
}

export function createHiddenDice() {
  return Array.from({ length: DICE_PER_PLAYER }, () => 1 + Math.floor(Math.random() * 6));
}
