import { useState } from "react";
import { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getGameAIPlayers, getGameAISummary, getGameMemories } from "../../../api";
import AIChat from "../../../components/AIChat";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import "./index.css";

const NAMES = { gomoku: "五子棋", aeroplane: "飞行棋", landlord: "斗地主", jungle: "斗兽棋", chinese_chess: "中国象棋" };

/** Explainable AI companion page backed only by real local product records. */
export default function AIPage() {
  const [summary, setSummary] = useState(null);
  const [players, setPlayers] = useState([]);
  const [memories, setMemories] = useState([]);
  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    const id = getCustomerId();
    Promise.allSettled([getGameAISummary(id), getGameAIPlayers(), getGameMemories(id)]).then(([a, b, c]) => {
      if (a.status === "fulfilled") setSummary(a.value);
      if (b.status === "fulfilled") setPlayers(b.value);
      if (c.status === "fulfilled") setMemories(c.value);
    });
  });
  return <View className="page ai-page">
    <View className="ai-hero"><Text>DAILY COMPANION</Text><Text>今天的陪伴小结</Text><Text>不上传聊天内容，不猜测心情；只把真实的点菜、游戏和默契记录整理给你。</Text></View>
    <AIChat summary={summary} />
    <View className="ai-metrics"><View><Text>{summary?.meals || 0}</Text><Text>今日用餐</Text></View><View><Text>{summary?.games || 0}</Text><Text>今日游戏</Text></View><View><Text>+{summary?.love_score_change || 0}</Text><Text>默契变化</Text></View></View>
    <View className="ai-title"><Text>AI 陪练角色</Text><Text>规则公开可解释</Text></View>
    <View className="ai-player-list">{players.map((item) => <View key={`${item.game_type}-${item.level}`}><View><Text>{item.name.slice(0, 1)}</Text></View><View><Text>{item.name}</Text><Text>{NAMES[item.game_type] || item.game_type} · {item.level === "random" ? "轻松随机" : "规则策略"}</Text></View><Text>{item.config?.reserved ? "预留" : "可用"}</Text></View>)}</View>
    <View className="ai-title"><Text>游戏记忆</Text><Text>{memories.length} 条</Text></View>
    <View className="memory-list">{memories.slice(0, 8).map((item) => <View key={item.id}><Text>{item.event === "FIRST_CHESS" ? "初" : "棋"}</Text><View><Text>{item.content}</Text><Text>{item.created_at?.slice(0, 10)}</Text></View></View>)}{!memories.length && <Text>完成一局游戏后，共同记忆会出现在这里。</Text>}</View>
  </View>;
}
