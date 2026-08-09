import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getCoupleScore, getCoupleScoreHistory } from "../../api";
import LoveScoreCard from "../../components/LoveScoreCard";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { dateLabel, EMPTY_COUPLE_SCORE } from "./helpers";
import "./index.css";

export default function CoupleHome() {
  const [summary, setSummary] = useState(EMPTY_COUPLE_SCORE);
  const [history, setHistory] = useState([]);
  const [offline, setOffline] = useState(false);

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    const customerId = getCustomerId();
    Promise.allSettled([
      getCoupleScore(customerId),
      getCoupleScoreHistory(customerId)
    ]).then(([scoreResult, historyResult]) => {
      if (scoreResult.status === "fulfilled") setSummary(scoreResult.value);
      if (historyResult.status === "fulfilled") setHistory(historyResult.value);
      setOffline(scoreResult.status === "rejected");
    });
  });

  const latest = history.find((entry) => dateLabel(entry.time) === "今天");
  return (
    <View className="page couple-page">
      <View className="couple-hero">
        <Text className="eyebrow">US, TOGETHER</Text>
        <Text>♥ 我们</Text>
        <Text>把每顿饭、每次鼓励和每段共同经历，慢慢存成属于两个人的成长记录。</Text>
      </View>

      <LoveScoreCard summary={summary} />

      <View className="couple-month-card">
        <View><Text>{summary.month_meals}</Text><Text>一起吃饭</Text></View>
        <View><Text>{summary.month_games}</Text><Text>一起游戏</Text></View>
        <View><Text>{summary.month_encouragement}</Text><Text>互相鼓励</Text></View>
      </View>

      <View className="couple-section-heading"><Text>今日互动</Text><Text>每一件小事都算数</Text></View>
      <View className="couple-latest-card">
        {latest ? (
          <><Text>+{latest.score}</Text><View><Text>{latest.description}</Text><Text>已经记入我们的积分流水</Text></View></>
        ) : (
          <><Text>0</Text><View><Text>今天还没有新的互动</Text><Text>完成一顿饭或留下五星评价就会自动记录</Text></View></>
        )}
      </View>

      <View className="couple-section-heading"><Text>共同成长</Text><Text>查看更完整的记录</Text></View>
      <View className="couple-link-grid">
        <View onClick={() => Taro.navigateTo({ url: "/pages/couple/score" })}><Text>积分明细</Text><Text>每一分从哪里来</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/couple/records" })}><Text>共同记录</Text><Text>第一次与最喜欢</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/couple/achievements" })}><Text>成就</Text><Text>看看解锁了什么</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/profile/index" })}><Text>口味收藏</Text><Text>继续查看她喜欢的菜</Text></View>
      </View>

      <View className="couple-admin-link" onClick={() => Taro.navigateTo({ url: "/pages/admin-login/index" })}>
        <View><Text>小厨房管理</Text><Text>订单、菜单和数据统计仍在这里</Text></View><Text>›</Text>
      </View>
      {offline && <Text className="couple-offline">默契值服务暂时没有连接，点餐功能不受影响。</Text>}
      <Text className="couple-formula-note">默契值由近期互动、共同经历和满意反馈综合计算，不等同于积分总数。</Text>
    </View>
  );
}
