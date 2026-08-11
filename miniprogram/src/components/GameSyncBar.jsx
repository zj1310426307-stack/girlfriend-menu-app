import { Text, View } from "@tarojs/components";

import "./GameSyncBar.css";

const COPY = {
  online: "棋局已同步",
  syncing: "正在同步棋局…",
  offline: "连接中断，棋局已暂停"
};

/** Persistent network state for turn-based rooms; never hides failures in a toast. */
export default function GameSyncBar({ status = "syncing", message = "", onRetry, compact = false }) {
  const normalized = ["online", "syncing", "offline"].includes(status) ? status : "syncing";
  const label = normalized === "offline" && message ? message : COPY[normalized];
  return (
    <View
      className={`game-sync-bar ${normalized} ${compact ? "compact" : ""}`}
      role="status"
      aria-live="polite"
    >
      <View className="game-sync-dot" />
      <Text>{label}</Text>
      {normalized === "offline" && onRetry && (
        <View
          className="game-sync-retry"
          role="button"
          aria-label="重新同步棋局"
          onClick={onRetry}
        ><Text>重试</Text></View>
      )}
    </View>
  );
}
