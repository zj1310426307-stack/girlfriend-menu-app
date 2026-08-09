import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getGameRanking } from "../../../api";
import { getCustomerId } from "../../../utils/customer";
import { ensureInvitePassed } from "../../../utils/invite";
import "./index.css";

const NAMES = { gomoku: "五子棋", aeroplane: "飞行棋", landlord: "斗地主", jungle: "斗兽棋", chinese_chess: "中国象棋", dice: "大话骰" };

/** Privacy-safe game data center for personal records and shared-room ranking. */
export default function RankingPage() {
  const [data, setData] = useState({ my_statistics: [], monthly_ranking: [], popular_games: [] });
  const [loading, setLoading] = useState(true);
  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    getGameRanking(getCustomerId()).then(setData).catch((error) => Taro.showToast({ title: error.message || "排行榜加载失败", icon: "none" })).finally(() => setLoading(false));
  });
  return <View className="page ranking-page">
    <View className="ranking-hero"><Text>GAME DATA</Text><Text>我们的游戏记录</Text><Text>只统计真实完成并写入服务器的对局，搭档身份已脱敏。</Text></View>
    <View className="ranking-title"><Text>我的战绩</Text><Text>{loading ? "同步中" : `${data.my_statistics.length} 类游戏`}</Text></View>
    <View className="ranking-stats">{data.my_statistics.length ? data.my_statistics.map((item) => <View key={item.game_type}><Text>{NAMES[item.game_type] || item.game_type}</Text><Text>{item.wins}<Text> 胜</Text></Text><View><Text>{item.total_games} 局</Text><Text>胜率 {item.win_rate}%</Text></View></View>) : <View className="ranking-empty"><Text>还没有完成过游戏</Text><Text>去“一起玩”完成第一局吧。</Text></View>}</View>
    <View className="ranking-title"><Text>本月默契榜</Text><Text>仅共同房间</Text></View>
    <View className="ranking-list">{data.monthly_ranking.map((item) => <View key={`${item.rank}-${item.display_name}`}><Text>{item.rank}</Text><View><Text>{item.display_name}</Text><Text>{item.total_games} 局 · 胜率 {item.win_rate}%</Text></View><Text>{item.wins} 胜</Text></View>)}</View>
    <View className="ranking-ai-entry" onClick={() => Taro.navigateTo({ url: "/pages/games/ai/index" })}><View><Text>今日陪伴小结</Text><Text>从点菜、游戏和默契值生成</Text></View><Text>→</Text></View>
  </View>;
}
