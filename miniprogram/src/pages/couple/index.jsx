import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import {
  getCoupleProfile,
  getCoupleScore,
  getCoupleScoreHistory,
  getCoupleStatistics,
  getNotificationUnreadCount,
  getTodayTasks
} from "../../api";
import LoveScoreCard from "../../components/LoveScoreCard";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { dateLabel, EMPTY_COUPLE_SCORE } from "./helpers";
import "./index.css";

export default function CoupleHome() {
  const [summary, setSummary] = useState(EMPTY_COUPLE_SCORE);
  const [history, setHistory] = useState([]);
  const [offline, setOffline] = useState(false);
  const [tasks, setTasks] = useState(null);
  const [profile, setProfile] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [unread, setUnread] = useState(0);

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    const customerId = getCustomerId();
    Promise.allSettled([
      getCoupleScore(customerId),
      getCoupleScoreHistory(customerId),
      getTodayTasks(customerId),
      getCoupleProfile(customerId),
      getCoupleStatistics(customerId),
      getNotificationUnreadCount(customerId)
    ]).then(([scoreResult, historyResult, tasksResult, profileResult, statisticsResult, unreadResult]) => {
      if (scoreResult.status === "fulfilled") setSummary(scoreResult.value);
      if (historyResult.status === "fulfilled") setHistory(historyResult.value);
      if (tasksResult.status === "fulfilled") setTasks(tasksResult.value);
      if (profileResult.status === "fulfilled") setProfile(profileResult.value);
      if (statisticsResult.status === "fulfilled") setStatistics(statisticsResult.value);
      if (unreadResult.status === "fulfilled") setUnread(unreadResult.value?.count || 0);
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

      <View className="couple-profile-card" onClick={() => Taro.navigateTo({ url: "/pages/couple/timeline" })}>
        <View><Text>{profile?.days_together || 1}</Text><Text>一起走过的日子</Text></View>
        <View><Text>{profile?.record_count || 0}</Text><Text>共同记录</Text></View>
        <View><Text>{profile?.next_date_days ?? "—"}</Text><Text>{profile?.next_date_title || "距离下个纪念日"}</Text></View>
      </View>

      <View className="couple-message-entry" onClick={() => Taro.navigateTo({ url: "/pages/notifications/index" })}><View><Text>消息与提醒</Text><Text>{unread ? `${unread} 条未读消息` : "重要的进度都收在这里"}</Text></View>{unread > 0 && <Text>{unread > 99 ? "99+" : unread}</Text>}<Text>›</Text></View>

      <View className="couple-month-card">
        <View><Text>{summary.month_meals}</Text><Text>一起吃饭</Text></View>
        <View><Text>{summary.month_games}</Text><Text>一起游戏</Text></View>
        <View><Text>{summary.month_encouragement}</Text><Text>互相鼓励</Text></View>
      </View>

      <View className="couple-section-heading"><Text>今日互动</Text><Text>每一件小事都算数</Text></View>
      <View className="couple-tasks-entry" onClick={() => Taro.navigateTo({ url: "/pages/couple/tasks" })}>
        <View><Text>{tasks?.completed_count || 0}/{tasks?.total_count || 4}</Text><Text>今日任务</Text></View>
        <View><Text>一起完成今天的小事</Text><Text>已获得 +{tasks?.earned_score || 0} 默契积分</Text></View>
        <Text>›</Text>
      </View>
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
        <View onClick={() => Taro.navigateTo({ url: "/pages/couple/game-records" })}><Text>游戏记录</Text><Text>胜负与一起玩过的时光</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/couple/tasks" })}><Text>每日任务</Text><Text>今天的小互动与奖励</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/couple/achievements" })}><Text>成就</Text><Text>看看解锁了什么</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/couple/timeline" })}><Text>我们的故事</Text><Text>时间轴与纪念日</Text></View>
        <View onClick={() => Taro.navigateTo({ url: "/pages/profile/index" })}><Text>口味收藏</Text><Text>继续查看她喜欢的菜</Text></View>
      </View>

      <View className="couple-admin-link" onClick={() => Taro.navigateTo({ url: "/pages/admin-login/index" })}>
        <View><Text>小厨房管理</Text><Text>订单、菜单和数据统计仍在这里</Text></View><Text>›</Text>
      </View>
      {offline && <Text className="couple-offline">默契值服务暂时没有连接，点餐功能不受影响。</Text>}
      {statistics && <Text className="couple-formula-note">到目前为止，我们留下了 {statistics.meals} 次点菜、{statistics.games} 局游戏和 {statistics.interactions} 条互动记录。</Text>}
      <Text className="couple-formula-note">默契值由近期互动、共同经历和满意反馈综合计算，不等同于积分总数。</Text>
    </View>
  );
}
