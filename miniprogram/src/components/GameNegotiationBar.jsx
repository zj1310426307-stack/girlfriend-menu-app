import { Text, View } from "@tarojs/components";

import { playFeedback } from "../utils/feedback";
import "./GameNegotiationBar.css";

const KIND_TEXT = {
  undo: { label: "悔棋", title: "想悔一步棋", detail: "同意后会回退到对方走这一步之前" },
  draw: { label: "求和", title: "想握手言和", detail: "同意后本局以和棋结束，双方各得参与分" }
};

/**
 * Consensual undo/draw negotiation banner for couple turn-based games.
 *
 * Shows the offerer a waiting state with cancel, and the other player
 * accept/decline actions. Rendered only while a negotiation is pending;
 * the server stays authoritative for every transition.
 */
export default function GameNegotiationBar({ negotiation, myId, busy = "", onAccept, onDecline, onCancel }) {
  if (!negotiation || !negotiation.by) return null;
  const kind = KIND_TEXT[negotiation.type];
  if (!kind) return null;
  const fromMe = negotiation.by === myId;
  const actionBusy = busy === "UNDO_ACCEPT" || busy === "DRAW_ACCEPT"
    || busy === "UNDO_DECLINE" || busy === "DRAW_DECLINE";

  if (fromMe) {
    return (
      <View className="game-negotiation waiting">
        <View>
          <Text>已发起{kind.label}请求</Text>
          <Text>{kind.title}，等对方回应…</Text>
        </View>
        <View className={`game-negotiation-action ghost ${actionBusy ? "disabled" : ""}`} onClick={() => !actionBusy && onCancel?.()}>
          <Text>取消</Text>
        </View>
      </View>
    );
  }

  return (
    <View className="game-negotiation pending">
      <View>
        <Text>对方{kind.title}</Text>
        <Text>{kind.detail}</Text>
      </View>
      <View className="game-negotiation-actions">
        <View className={`game-negotiation-action ghost ${actionBusy ? "disabled" : ""}`} onClick={() => {
          if (actionBusy) return;
          playFeedback("tap", { haptic: false });
          onDecline?.();
        }}>
          <Text>拒绝</Text>
        </View>
        <View className={`game-negotiation-action solid ${actionBusy ? "disabled" : ""}`} onClick={() => {
          if (actionBusy) return;
          playFeedback("tap", { haptic: false });
          onAccept?.();
        }}>
          <Text>同意</Text>
        </View>
      </View>
    </View>
  );
}
