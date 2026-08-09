import { useState } from "react";
import { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getCoupleScoreHistory, getFavoriteRanking, getMyOrders } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { formatDate } from "./helpers";
import "./index.css";

export default function CoupleRecordsPage() {
  const [records, setRecords] = useState({ firstOrder: null, meals: 0, games: 0, favorite: "还在慢慢发现" });

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    const customerId = getCustomerId();
    Promise.allSettled([
      getMyOrders(customerId),
      getFavoriteRanking(customerId),
      getCoupleScoreHistory(customerId)
    ]).then(([ordersResult, rankingResult, historyResult]) => {
      const orders = ordersResult.status === "fulfilled" ? ordersResult.value : [];
      const ranking = rankingResult.status === "fulfilled" ? rankingResult.value : [];
      const history = historyResult.status === "fulfilled" ? historyResult.value : [];
      const firstOrder = [...orders].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))[0];
      setRecords({
        firstOrder: firstOrder?.created_at || null,
        meals: orders.filter((order) => order.status === "已完成").length,
        games: history.filter((entry) => entry.type === "GAME_PLAY").length,
        favorite: ranking[0]?.name || "还在慢慢发现"
      });
    });
  });

  return (
    <View className="page couple-subpage">
      <View className="couple-subhead"><Text className="eyebrow">OUR MEMORIES</Text><Text>我们的记录</Text><Text>不是排行榜，是两个人一起生活留下来的痕迹。</Text></View>
      <View className="couple-record-list">
        <View><Text>第一次点餐</Text><Text>{formatDate(records.firstOrder)}</Text><Text>故事从第一张点菜单开始</Text></View>
        <View><Text>一起完成晚餐</Text><Text>{records.meals} 次</Text><Text>只统计状态为“已完成”的订单</Text></View>
        <View><Text>一起玩游戏</Text><Text>{records.games} 次</Text><Text>游戏积分将在后续版本自动接入</Text></View>
        <View className="favorite"><Text>她最喜欢</Text><Text>{records.favorite}</Text><Text>根据点单、收藏和评价综合计算</Text></View>
      </View>
    </View>
  );
}
