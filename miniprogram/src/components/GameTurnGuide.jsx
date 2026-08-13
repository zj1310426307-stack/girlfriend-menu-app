import { Button, Text, View } from "@tarojs/components";

import "./GameTurnGuide.css";

/** Keep the next required game action visible above large boards. */
export default function GameTurnGuide({ marker = "·", title, detail = "", tone = "active", actionLabel = "", onAction, shareLabel = "" }) {
  return (
    <View className={`game-turn-guide ${tone}`} role="status" aria-live="polite">
      <View className="game-turn-marker"><Text>{marker}</Text></View>
      <View className="game-turn-copy">
        <Text>{title}</Text>
        {detail && <Text>{detail}</Text>}
      </View>
      {shareLabel ? (
        <Button className="game-turn-action share" openType="share">{shareLabel}</Button>
      ) : actionLabel && onAction && (
        <View className="game-turn-action" role="button" onClick={onAction}><Text>{actionLabel}</Text></View>
      )}
    </View>
  );
}
