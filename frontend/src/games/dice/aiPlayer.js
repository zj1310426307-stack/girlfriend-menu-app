import {
  DICE_PER_PLAYER,
  getNextLegalBid,
} from "./gameLogic";

/**
 * Counts how many of the AI's private dice support a given face.
 */
function countPrivateSupport(dice, face) {
  return dice.filter((value) => value === face || (face !== 1 && value === 1)).length;
}

/**
 * Picks the face best supported by the AI's own hidden dice.
 */
function chooseSupportedFace(dice) {
  const scores = Array.from({ length: 6 }, (_, index) => ({
    face: index + 1,
    count: countPrivateSupport(dice, index + 1),
  }));
  scores.sort((left, right) => right.count - left.count || Math.random() - 0.5);
  return scores[0].face;
}

/**
 * Chooses a simple probability-aware AI action: raise or challenge.
 */
export function chooseAiAction({ currentBid, ownDice, playerCount }) {
  const maxQuantity = playerCount * DICE_PER_PLAYER;
  const preferredFace = chooseSupportedFace(ownDice);

  if (!currentBid) {
    const ownSupport = countPrivateSupport(ownDice, preferredFace);
    const expectedOthers = (maxQuantity - DICE_PER_PLAYER) * (preferredFace === 1 ? 1 / 6 : 1 / 3);
    return {
      type: "bid",
      bid: {
        quantity: Math.max(1, Math.min(maxQuantity, Math.floor(ownSupport + expectedOthers * 0.55))),
        face: preferredFace,
      },
    };
  }

  const privateSupport = countPrivateSupport(ownDice, currentBid.face);
  const unknownDice = maxQuantity - DICE_PER_PLAYER;
  const expectedUnknown = unknownDice * (currentBid.face === 1 ? 1 / 6 : 1 / 3);
  const expectedTotal = privateSupport + expectedUnknown;
  const pressure = currentBid.quantity - expectedTotal;
  const challengeChance = Math.min(0.92, Math.max(0.05, 0.2 + pressure * 0.22));

  if (Math.random() < challengeChance) {
    return { type: "open" };
  }

  const raiseQuantity =
    currentBid.quantity + (Math.random() < 0.72 ? 0 : 1);
  const raiseFace =
    Math.random() < 0.58 ? preferredFace : currentBid.face + 1;
  const bid = getNextLegalBid(currentBid, raiseQuantity, raiseFace, maxQuantity);
  return bid ? { type: "bid", bid } : { type: "open" };
}
