import { useCallback, useState } from "react";
import Taro, { useDidShow, usePullDownRefresh } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { completeTodayTask, getTodayTasks } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import "./tasks.css";

const META = {
  COMPLIMENT: { icon: "夸", note: "认真说出口后，由你点亮" },
  MEAL: { icon: "餐", note: "订单完成后自动点亮" },
  GAME: { icon: "玩", note: "双人游戏结束后自动点亮" },
  REVIEW: { icon: "评", note: "提交五星评价后自动点亮" }
};

export default function CoupleTasksPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setSummary(await getTodayTasks(getCustomerId()));
      setError("");
    } catch (requestError) {
      setError(requestError.message || "今日任务加载失败");
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, []);

  useDidShow(() => {
    if (ensureInvitePassed()) load();
  });
  usePullDownRefresh(load);

  const complete = async (task) => {
    if (task.type !== "COMPLIMENT" || task.status === "completed" || completing) return;
    setCompleting(task.id);
    try {
      await completeTodayTask(getCustomerId(), task.id);
      Taro.vibrateShort({ type: "light" }).catch(() => {});
      Taro.showToast({ title: `默契 +${task.reward_score}`, icon: "success" });
      await load();
    } catch (requestError) {
      Taro.showToast({ title: requestError.message || "暂时无法完成", icon: "none" });
    } finally {
      setCompleting(null);
    }
  };

  const total = summary?.total_count || 0;
  const completed = summary?.completed_count || 0;
  const progress = total ? Math.round(completed / total * 100) : 0;

  return (
    <View className="couple-tasks-page">
      <View className="tasks-hero">
        <Text>DAILY TOGETHER</Text>
        <Text>今天也要好好互动</Text>
        <Text>任务不是打卡压力，只是给平常的小事一个被记住的理由。</Text>
      </View>

      <View className="tasks-progress-card">
        <View><Text>今日进度</Text><Text>{completed}/{total || 4}</Text></View>
        <View className="tasks-progress-track"><View style={{ width: `${progress}%` }} /></View>
        <View><Text>已获得 +{summary?.earned_score || 0}</Text><Text>全部完成 +{summary?.possible_score || 13}</Text></View>
      </View>

      {loading && <View className="tasks-state"><Text>正在准备今天的小任务…</Text></View>}
      {error && <View className="tasks-state error" onClick={load}><Text>{error}</Text><Text>点这里重试</Text></View>}

      {!loading && !error && (
        <View className="tasks-list">
          {(summary?.tasks || []).map((task) => {
            const meta = META[task.type] || { icon: "♥", note: "完成后自动记录" };
            const done = task.status === "completed";
            const manual = task.type === "COMPLIMENT";
            return (
              <View key={task.id} className={`tasks-row ${done ? "completed" : ""}`}>
                <View className="tasks-icon"><Text>{done ? "✓" : meta.icon}</Text></View>
                <View className="tasks-copy"><Text>{task.title}</Text><Text>{done ? "今天已经完成" : meta.note}</Text></View>
                <View className={`tasks-reward ${manual && !done ? "action" : ""}`} onClick={() => complete(task)}>
                  <Text>{completing === task.id ? "…" : done ? "已完成" : `+${task.reward_score}`}</Text>
                </View>
              </View>
            );
          })}
        </View>
      )}

      <View className="tasks-section-title"><Text>最近互动</Text><Text>飞行棋事件会留在这里</Text></View>
      <View className="tasks-interactions">
        {(summary?.recent_interactions || []).length === 0 && <View className="tasks-empty"><Text>还没有随机互动记录</Text><Text>去玩一局情侣飞行棋，也许会遇到惊喜。</Text></View>}
        {(summary?.recent_interactions || []).map((item) => (
          <View key={item.id}>
            <Text>♥</Text>
            <View><Text>{item.content}</Text><Text>{item.status === "completed" ? "已经一起完成" : "等待完成"}</Text></View>
            <Text>+{item.score}</Text>
          </View>
        ))}
      </View>

      <View className="tasks-game-link" onClick={() => Taro.navigateTo({ url: "/pages/games/flight/index" })}>
        <View><Text>去玩情侣飞行棋</Text><Text>掷骰子，遇见今天的随机互动</Text></View><Text>›</Text>
      </View>
    </View>
  );
}
