import { useState } from "react";
import { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getCoupleScore, getCoupleScoreHistory } from "../../api";
import LoveScoreCard from "../../components/LoveScoreCard";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { dateLabel, EMPTY_COUPLE_SCORE } from "./helpers";
import "./index.css";

export default function CoupleScorePage() {
  const [summary, setSummary] = useState(EMPTY_COUPLE_SCORE);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    const customerId = getCustomerId();
    setLoading(true);
    Promise.all([getCoupleScore(customerId), getCoupleScoreHistory(customerId)])
      .then(([nextSummary, nextHistory]) => {
        setSummary(nextSummary);
        setHistory(nextHistory);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  });

  let previousLabel = "";
  return (
    <View className="page couple-subpage">
      <View className="couple-subhead"><Text className="eyebrow">LOVE SCORE</Text><Text>积分记录</Text><Text>积分是行为流水，默契值是综合成长结果。</Text></View>
      <LoveScoreCard summary={summary} compact />
      {loading && <View className="state-box"><Text>正在整理我们的积分…</Text></View>}
      {!loading && history.length === 0 && <View className="couple-empty"><Text>还没有积分记录</Text><Text>完成订单后，这里会出现第一条共同记录。</Text></View>}
      <View className="couple-score-list">
        {history.map((entry) => {
          const label = dateLabel(entry.time);
          const showLabel = label !== previousLabel;
          previousLabel = label;
          return (
            <View key={entry.id}>
              {showLabel && <Text className="couple-day-label">{label}</Text>}
              <View className="couple-score-row"><Text>+{entry.score}</Text><View><Text>{entry.description}</Text><Text>{entry.type}</Text></View></View>
            </View>
          );
        })}
      </View>
    </View>
  );
}
