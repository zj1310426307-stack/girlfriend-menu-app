import { useEffect, useRef } from "react";

import { playSound } from "../utils/feedback";

/**
 * Play a gentle two-note chime once when a game transitions into its
 * finished phase and the local player won. Losing stays silent on purpose:
 * no salt in a couple's kitchen. Rematching resets the latch so a second
 * win in the same page session still chimes.
 */
export default function useGameFinishFeedback(isFinished, didWin) {
  const playedRef = useRef(false);
  useEffect(() => {
    if (!isFinished) {
      playedRef.current = false;
      return;
    }
    if (playedRef.current) return;
    playedRef.current = true;
    if (didWin) playSound("win");
  }, [isFinished, didWin]);
}
