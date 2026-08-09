import { Text, View } from "@tarojs/components";

import "./AIChat.css";

/** Explain the deterministic daily summary instead of impersonating a remote LLM. */
export default function AIChat({ summary }) {
  return (
    <View className="ai-chat-card">
      <View className="ai-avatar"><Text>伴</Text></View>
      <View><Text>{summary?.message || "正在整理今天的共同记录…"}</Text><Text>{summary?.recommendation || "先做一件都喜欢的小事吧。"}</Text></View>
    </View>
  );
}
