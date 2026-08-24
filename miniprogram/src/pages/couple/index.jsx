import { useRef, useState } from "react";
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
import PageSyncNotice from "../../components/PageSyncNotice";
import { ROUTES } from "../../config/routes";
import { getAuthenticatedCustomerId, getCustomerId, hasCustomerSession } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import {
  claimPageRefresh,
  PAGE_SNAPSHOT_MAX_AGE,
  readPageSnapshot,
  releasePageRefresh,
  writePageSnapshot
} from "../../utils/pageSnapshot";
import { dateLabel, EMPTY_COUPLE_SCORE } from "./helpers";
import "./index.css";

/** Restore one complete couple dashboard snapshot before the six online reads finish. */
function createInitialCoupleState() {
  if (!hasCustomerSession()) return null;
  const customerId = getAuthenticatedCustomerId();
  const snapshot = readPageSnapshot("couple", customerId, PAGE_SNAPSHOT_MAX_AGE.couple);
  const complete = snapshot?.summary
    && Array.isArray(snapshot.history)
    && snapshot.tasks
    && snapshot.profile
    && snapshot.statistics
    && Number.isFinite(snapshot.unread);
  if (!complete) return null;
  return snapshot;
}

/** Couple home owns its complete read snapshot while domain pages own mutations. */
export default function CoupleHome() {
  const [initialCouple] = useState(createInitialCoupleState);
  const [summary, setSummary] = useState(initialCouple?.summary || EMPTY_COUPLE_SCORE);
  const [history, setHistory] = useState(initialCouple?.history || []);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(!initialCouple);
  const [tasks, setTasks] = useState(initialCouple?.tasks || null);
  const [profile, setProfile] = useState(initialCouple?.profile || null);
  const [statistics, setStatistics] = useState(initialCouple?.statistics || null);
  const [unread, setUnread] = useState(initialCouple?.unread || 0);
  const coupleLoadingRef = useRef(false);

  /** Refresh all dashboard summaries once and persist only a complete successful set. */
  const loadCouple = async ({ force = false } = {}) => {
    if (!ensureInvitePassed()) return;
    if (coupleLoadingRef.current) return;
    const customerId = getCustomerId();
    if (!claimPageRefresh("couple", customerId, { force })) return;
    coupleLoadingRef.current = true;
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        getCoupleScore(customerId),
        getCoupleScoreHistory(customerId),
        getTodayTasks(customerId),
        getCoupleProfile(customerId),
        getCoupleStatistics(customerId),
        getNotificationUnreadCount(customerId)
      ]);
      const [scoreResult, historyResult, tasksResult, profileResult, statisticsResult, unreadResult] = results;
      if (scoreResult.status === "fulfilled") setSummary(scoreResult.value);
      if (historyResult.status === "fulfilled") setHistory(historyResult.value);
      if (tasksResult.status === "fulfilled") setTasks(tasksResult.value);
      if (profileResult.status === "fulfilled") setProfile(profileResult.value);
      if (statisticsResult.status === "fulfilled") setStatistics(statisticsResult.value);
      if (unreadResult.status === "fulfilled") setUnread(unreadResult.value?.count || 0);
      setOffline(results.some((result) => result.status === "rejected"));
      if (results.every((result) => result.status === "fulfilled")) {
        writePageSnapshot("couple", customerId, {
          summary: scoreResult.value,
          history: historyResult.value,
          tasks: tasksResult.value,
          profile: profileResult.value,
          statistics: statisticsResult.value,
          unread: unreadResult.value?.count || 0
        });
      } else {
        releasePageRefresh("couple", customerId);
      }
    } catch (error) {
      releasePageRefresh("couple", customerId);
      setOffline(true);
    } finally {
      setLoading(false);
      coupleLoadingRef.current = false;
    }
  };

  useDidShow(() => {
    loadCouple();
  });

  const latest = history.find((entry) => dateLabel(entry.time) === "今天");
  return (
    <View className="page couple-page">
      <View className="couple-hero">
        <Text className="eyebrow">US, TOGETHER</Text>
        <Text>♥ 我们</Text>
        <Text>把每顿饭、每次鼓励和每段共同经历，慢慢存成属于两个人的成长记录。</Text>
      </View>

      <PageSyncNotice loading={loading} offline={offline} onRetry={() => loadCouple({ force: true })} />

      <LoveScoreCard summary={summary} />

      <View className="couple-profile-card" onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_TIMELINE })}>
        <View><Text>{profile?.days_together || 1}</Text><Text>一起走过的日子</Text></View>
        <View><Text>{profile?.record_count || 0}</Text><Text>共同记录</Text></View>
        <View><Text>{profile?.next_date_days ?? "—"}</Text><Text>{profile?.next_date_title || "距离下个纪念日"}</Text></View>
      </View>

      <View className="couple-message-entry" onClick={() => Taro.navigateTo({ url: ROUTES.NOTIFICATIONS })}><View><Text>消息与提醒</Text><Text>{unread ? `${unread} 条未读消息` : "重要的进度都收在这里"}</Text></View>{unread > 0 && <Text>{unread > 99 ? "99+" : unread}</Text>}<Text>›</Text></View>

      <View className="couple-month-card">
        <View><Text>{summary.month_meals}</Text><Text>一起吃饭</Text></View>
        <View><Text>{summary.month_games}</Text><Text>一起游戏</Text></View>
        <View><Text>{summary.month_encouragement}</Text><Text>互相鼓励</Text></View>
      </View>

      <View className="couple-section-heading"><Text>今日互动</Text><Text>每一件小事都算数</Text></View>
      <View className="couple-tasks-entry" onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_TASKS })}>
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
        <View onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_SCORE })}><Text>积分明细</Text><Text>每一分从哪里来</Text></View>
        <View onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_RECORDS })}><Text>共同记录</Text><Text>第一次与最喜欢</Text></View>
        <View onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_GAME_RECORDS })}><Text>游戏记录</Text><Text>胜负与一起玩过的时光</Text></View>
        <View onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_TASKS })}><Text>每日任务</Text><Text>今天的小互动与奖励</Text></View>
        <View onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_ACHIEVEMENTS })}><Text>成就</Text><Text>看看解锁了什么</Text></View>
        <View onClick={() => Taro.navigateTo({ url: ROUTES.COUPLE_TIMELINE })}><Text>我们的故事</Text><Text>时间轴与纪念日</Text></View>
        <View onClick={() => Taro.navigateTo({ url: ROUTES.PROFILE })}><Text>口味收藏</Text><Text>继续查看她喜欢的菜</Text></View>
      </View>

      <View className="couple-admin-link" onClick={() => Taro.navigateTo({ url: ROUTES.ADMIN_LOGIN })}>
        <View><Text>小厨房管理</Text><Text>订单、菜单和数据统计仍在这里</Text></View><Text>›</Text>
      </View>
      {offline && <Text className="couple-offline">默契值服务暂时没有连接，点餐功能不受影响。</Text>}
      {statistics && <Text className="couple-formula-note">到目前为止，我们留下了 {statistics.meals} 次点菜、{statistics.games} 局游戏和 {statistics.interactions} 条互动记录。</Text>}
      <Text className="couple-formula-note">默契值由近期互动、共同经历和满意反馈综合计算，不等同于积分总数。</Text>
    </View>
  );
}
