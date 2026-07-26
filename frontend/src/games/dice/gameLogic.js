export const DICE_PER_PLAYER = 5;
export const MIN_PLAYERS = 2;
export const MAX_PLAYERS = 6;

const AI_NAMES = ["玩家A", "玩家B", "玩家C", "玩家D", "玩家E"];

/**
 * Builds the player list for the selected local game size.
 */
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

/**
 * Returns the player after the supplied player in table order.
 */
export function getNextPlayer(players, currentPlayerId) {
  const currentIndex = players.findIndex((player) => player.id === currentPlayerId);
  return players[(currentIndex + 1 + players.length) % players.length];
}

/**
 * Checks whether a bid is strictly higher than the current bid.
 */
export function isHigherBid(currentBid, nextBid) {
  if (!nextBid || nextBid.quantity < 1 || nextBid.face < 1 || nextBid.face > 6) {
    return false;
  }
  if (!currentBid) {
    return true;
  }
  return (
    nextBid.quantity > currentBid.quantity ||
    (nextBid.quantity === currentBid.quantity && nextBid.face > currentBid.face)
  );
}

/**
 * Finds the smallest legal bid at or above a preferred quantity and face.
 */
export function getNextLegalBid(currentBid, preferredQuantity, preferredFace, maxQuantity) {
  let quantity = Math.min(maxQuantity, Math.max(1, preferredQuantity));
  let face = Math.min(6, Math.max(1, preferredFace));

  if (isHigherBid(currentBid, { quantity, face })) {
    return { quantity, face };
  }

  if (currentBid.face < 6) {
    return { quantity: currentBid.quantity, face: currentBid.face + 1 };
  }

  quantity = currentBid.quantity + 1;
  if (quantity > maxQuantity) {
    return null;
  }
  return { quantity, face: 1 };
}

/**
 * Counts matching dice. Ones are wild unless the bid itself is for ones.
 */
export function countMatchingDice(resultsByPlayer, face) {
  return Object.values(resultsByPlayer)
    .flat()
    .filter((value) => value === face || (face !== 1 && value === 1)).length;
}

/**
 * Resolves an "open" action and returns the winner, loser and actual count.
 */
export function resolveChallenge({ bid, challengerId, resultsByPlayer }) {
  if (!bid) {
    return null;
  }
  const actualCount = countMatchingDice(resultsByPlayer, bid.face);
  const bidSucceeded = actualCount >= bid.quantity;
  return {
    actualCount,
    bidSucceeded,
    winnerId: bidSucceeded ? bid.bidderId : challengerId,
    loserId: bidSucceeded ? challengerId : bid.bidderId,
  };
}

/**
 * Formats a bid for the Chinese game interface.
 */
export function formatBid(bid) {
  return bid ? `${bid.quantity}个${bid.face}` : "还没有人叫骰";
}

/**
 * Creates repeatable launch randomness without deciding any dice result.
 */
export function createSeededRandom(seedText) {
  let seed = 2166136261;
  for (let index = 0; index < seedText.length; index += 1) {
    seed ^= seedText.charCodeAt(index);
    seed = Math.imul(seed, 16777619);
  }
  return () => {
    seed += 0x6d2b79f5;
    let value = seed;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Produces randomized physical launch parameters for five dice.
 */
export function createPhysicalLaunches(playerId, roundId) {
  const random = createSeededRandom(`${playerId}-${roundId}-${Date.now()}`);
  return Array.from({ length: DICE_PER_PLAYER }, (_, index) => {
    const lane = index - (DICE_PER_PLAYER - 1) / 2;
    return {
      position: [
        lane * 0.7 + (random() - 0.5) * 0.35,
        3.4 + index * 0.38 + random() * 0.8,
        (random() - 0.5) * 1.5,
      ],
      rotation: [random() * Math.PI, random() * Math.PI, random() * Math.PI],
      linearVelocity: [
        (random() - 0.5) * 6.5,
        1.5 + random() * 3.2,
        (random() - 0.5) * 6.5,
      ],
      angularVelocity: [
        (random() - 0.5) * 25,
        (random() - 0.5) * 25,
        (random() - 0.5) * 25,
      ],
    };
  });
}
