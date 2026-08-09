import { useState } from "react";
import { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getCoupleScore, getCoupleScoreHistory, getMyOrders } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { EMPTY_COUPLE_SCORE } from "./helpers";
import "./index.css";

export default function CoupleAchievementsPage() {
  const [summary, setSummary] = useState(EMPTY_COUPLE_SCORE);
  const [completedMeals, setCompletedMeals] = useState(0);
  const [gamePlays, setGamePlays] = useState(0);
  const [reviewCount, setReviewCount] = useState(0);

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    const customerId = getCustomerId();
    Promise.allSettled([
      getCoupleScore(customerId),
      getMyOrders(customerId),
      getCoupleScoreHistory(customerId)
    ]).then(([scoreResult, ordersResult, historyResult]) => {
      const history = historyResult.status === "fulfilled" ? historyResult.value : [];
      const orders = ordersResult.status === "fulfilled" ? ordersResult.value : [];
      if (scoreResult.status === "fulfilled") setSummary(scoreResult.value);
      setCompletedMeals(orders.filter((order) => order.status === "已完成").length);
      setGamePlays(history.filter((entry) => entry.type === "GAME_PLAY").length);
      setReviewCount(history.filter((entry) => entry.type === "ORDER_REVIEW").length);
    });
  });

  const achievements = [
    { icon: "餐", title: "第一顿饭", desc: "完成第一次晚餐", value: completedMeals, target: 1 },
    { icon: "厨", title: "厨房新人", desc: "完成 10 次做饭", value: completedMeals, target: 10 },
    { icon: "伴", title: "甜蜜搭档", desc: "累计获得 100 积分", value: summary.points_total, target: 100 },
    { icon: "评", title: "五星鼓励", desc: "留下 5 次五星评价", value: reviewCount, target: 5 },
    { icon: "玩", title: "游戏情侣", desc: "一起完成 20 次游戏", value: gamePlays, target: 20 }
  ];

  return (
    <View className="page couple-subpage">
      <View className="couple-subhead"><Text className="eyebrow">ACHIEVEMENTS</Text><Text>我们的成就</Text><Text>不用着急解锁，认真生活就会慢慢亮起来。</Text></View>
      <View className="couple-achievement-list">
        {achievements.map((item) => {
          const unlocked = item.value >= item.target;
          const progress = Math.min(100, Math.round(item.value / item.target * 100));
          return (
            <View key={item.title} className={unlocked ? "unlocked" : ""}>
              <View><Text>{unlocked ? "✓" : item.icon}</Text></View>
              <View><Text>{item.title}</Text><Text>{item.desc}</Text><View><View style={{ width: `${progress}%` }} /></View><Text>{Math.min(item.value, item.target)} / {item.target}</Text></View>
            </View>
          );
        })}
      </View>
    </View>
  );
}
