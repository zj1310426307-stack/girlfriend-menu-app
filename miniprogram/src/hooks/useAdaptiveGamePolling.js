import { useEffect, useRef } from "react";
import { useDidHide, useDidShow } from "@tarojs/taro";

/**
 * Poll a couple game without overlapping requests or refreshing in background.
 * The next request is scheduled only after the previous one has completed.
 */
export default function useAdaptiveGamePolling({ enabled, load, interval = 1400 }) {
  const activeRef = useRef(true);
  const loadRef = useRef(load);
  const intervalRef = useRef(interval);

  loadRef.current = load;
  intervalRef.current = interval;

  useDidShow(() => { activeRef.current = true; });
  useDidHide(() => { activeRef.current = false; });

  useEffect(() => {
    if (!enabled) return undefined;
    let stopped = false;
    let timer = null;

    const schedule = () => {
      if (stopped) return;
      timer = setTimeout(tick, Math.max(800, Number(intervalRef.current) || 1400));
    };
    const tick = async () => {
      if (!stopped && activeRef.current) {
        try { await loadRef.current?.(); } catch (_) {}
      }
      schedule();
    };

    schedule();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [enabled]);
}
