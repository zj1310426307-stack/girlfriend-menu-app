import { DICE_PER_PLAYER, getNextLegalBid } from "./gameLogic";

function countPrivateSupport(dice, face) {
  return dice.filter((value) => value === face || (face !== 1 && value === 1)).length;
}

function chooseSupportedFace(dice) {
  const scores = Array.from({ length: 6 }, (_, index) => ({
    face: index + 1,
    count: countPrivateSupport(dice, index + 1),
  }));
  scores.sort((left, right) => right.count - left.count || Math.random() - 0.5);
  return scores[0].face;
}

function combination(n, k) {
  if (k < 0 || k > n) return 0;
  let result = 1;
  for (let index = 1; index <= Math.min(k, n - k); index += 1) {
    result = (result * (n - index + 1)) / index;
  }
  return result;
}

/** Estimate whether a bid is true from the AI's private dice and wild-one rule. */
export function estimateBidProbability({ quantity, face, ownDice = [], playerCount }) {
  const ownSupport = countPrivateSupport(ownDice, face);
  const needed = quantity - ownSupport;
  const unknown = Math.max(0, playerCount * DICE_PER_PLAYER - ownDice.length);
  if (needed <= 0) return 1;
  if (needed > unknown) return 0;
  const probability = face === 1 ? 1 / 6 : 1 / 3;
  let result = 0;
  for (let hits = needed; hits <= unknown; hits += 1) {
    result += combination(unknown, hits) * (probability ** hits) * ((1 - probability) ** (unknown - hits));
  }
  return Math.min(1, Math.max(0, result));
}

export function chooseAiAction({ currentBid, ownDice, playerCount }) {
  const maxQuantity = playerCount * DICE_PER_PLAYER;
  const preferredFace = chooseSupportedFace(ownDice || []);

  if (!currentBid) {
    const ownSupport = countPrivateSupport(ownDice || [], preferredFace);
    const expectedOthers = (maxQuantity - DICE_PER_PLAYER) * (preferredFace === 1 ? 1 / 6 : 1 / 3);
    let quantity = Math.max(1, Math.min(maxQuantity, Math.floor(ownSupport + expectedOthers)));
    while (quantity > 1 && estimateBidProbability({ quantity, face: preferredFace, ownDice, playerCount }) < 0.7) {
      quantity -= 1;
    }
    return {
      type: "bid",
      bid: {
        quantity,
        face: preferredFace,
      },
    };
  }

  const truthProbability = estimateBidProbability({
    quantity: currentBid.quantity,
    face: currentBid.face,
    ownDice,
    playerCount,
  });
  const challengeChance = Math.min(0.96, Math.max(0.04, 0.72 - truthProbability));

  if (Math.random() < challengeChance) return { type: "open" };

  const candidate = getNextLegalBid(currentBid, currentBid.quantity, preferredFace, maxQuantity);
  const candidateProbability = candidate ? estimateBidProbability({ ...candidate, ownDice, playerCount }) : 0;
  const bid = candidateProbability >= 0.4
    ? candidate
    : getNextLegalBid(currentBid, currentBid.quantity, currentBid.face + 1, maxQuantity);
  return bid ? { type: "bid", bid } : { type: "open" };
}
