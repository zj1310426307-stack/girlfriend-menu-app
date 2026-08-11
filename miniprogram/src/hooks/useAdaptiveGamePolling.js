import { useEffect, useRef } from "react";
import { useDidHide, useDidShow } from "@tarojs/taro";

/**
 * Poll a couple game without overlapping requests or refreshing in background.
 * The next request is scheduled only after the previous one has completed.
 */
export default function useAdaptiveGamePolling({
  enabled,
  load,
  interval = 1400,
  maxInterval = 12000,
  onStatus,
  onError
}) {
  const activeRef = useRef(true);
  const loadRef = useRef(load);
  const intervalRef = useRef(interval);
  const statusRef = useRef(onStatus);
  const errorRef = useRef(onError);

  loadRef.current = load;
  intervalRef.current = interval;
  statusRef.current = onStatus;
  errorRef.current = onError;

  useDidShow(() => { activeRef.current = true; });
  useDidHide(() => { activeRef.current = false; });

  useEffect(() => {
    if (!enabled) return undefined;
    let stopped = false;
    let timer = null;
    let failures = 0;

    const schedule = (delay = intervalRef.current) => {
      if (stopped) return;
      timer = setTimeout(tick, Math.max(800, Number(delay) || 1400));
    };
    const tick = async () => {
      if (!stopped && activeRef.current) {
        try {
          await loadRef.current?.();
          failures = 0;
          statusRef.current?.("online");
        } catch (error) {
          failures += 1;
          statusRef.current?.("offline");
          errorRef.current?.(error);
        }
      }
      const backoff = failures
        ? Math.min(maxInterval, (Number(intervalRef.current) || 1400) * (2 ** Math.min(failures, 3)))
        : intervalRef.current;
      schedule(backoff);
    };

    statusRef.current?.("syncing");
    tick();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }, [enabled]);
}
