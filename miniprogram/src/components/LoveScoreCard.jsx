import { Text, View } from "@tarojs/components";

import "./LoveScoreCard.css";

const EMPTY_SCORE = {
  total: 0,
  level: "初识",
  month_score: 0,
  points_total: 0,
  progress: 0
};

export default function LoveScoreCard({ summary, compact = false, onOpen, className = "" }) {
  const value = summary || EMPTY_SCORE;
  const progress = Math.max(0, Math.min(100, Number(value.progress) || 0));
  return (
    <View className={`love-score-card ${compact ? "is-compact" : ""} ${className}`.trim()} onClick={onOpen}>
      <View className="love-score-heading">
        <View><Text>♥</Text><Text>我们的默契值</Text></View>
        <Text>{value.level}</Text>
      </View>
      <View className="love-score-main">
        <Text>{value.total}</Text>
        <View><View style={{ width: `${progress}%` }} /></View>
      </View>
      <View className="love-score-foot">
        <Text>本月 +{value.month_score || 0}</Text>
        <Text>累计 {value.points_total || 0} 积分{onOpen ? " · 查看成长" : ""}</Text>
      </View>
    </View>
  );
}
