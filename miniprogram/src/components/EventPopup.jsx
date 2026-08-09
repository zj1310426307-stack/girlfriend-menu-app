import { Text, View } from "@tarojs/components";

import "./EventPopup.css";

const LABELS = { LOVE: "爱心互动", FOOD: "厨房时刻", FUN: "快乐挑战", TASK: "情侣任务" };

export default function EventPopup({ event, loading, onComplete }) {
  if (!event) return null;
  return (
    <View className="flight-event-mask">
      <View className="flight-event-card">
        <Text className="flight-event-mark">♥</Text>
        <Text className="flight-event-label">{LABELS[event.type] || "随机互动"}</Text>
        <Text className="flight-event-title">{event.content || "和对方完成一次温暖的小互动"}</Text>
        <Text className="flight-event-reward">完成后 +{event.score || 3} 默契积分</Text>
        <View className={loading ? "disabled" : ""} onClick={() => !loading && onComplete?.()}><Text>{loading ? "正在记录…" : "我们完成啦"}</Text></View>
        <Text className="flight-event-note">事件需要当前玩家确认，服务器只会奖励一次。</Text>
      </View>
    </View>
  );
}
