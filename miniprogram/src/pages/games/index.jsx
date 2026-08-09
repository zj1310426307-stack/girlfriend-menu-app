import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getGames } from "../../api";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const FALLBACK_GAMES = [
  { name: "大话骰", icon: "骰", type: "dice", status: "available" },
  { name: "五子棋", icon: "棋", type: "gomoku", status: "coming_soon" },
  { name: "飞行棋", icon: "飞", type: "aeroplane", status: "coming_soon" },
  { name: "斗地主", icon: "牌", type: "landlord", status: "coming_soon" },
  { name: "斗兽棋", icon: "兽", type: "jungle", status: "coming_soon" },
  { name: "中国象棋", icon: "象", type: "chinese_chess", status: "coming_soon" }
];

const GAME_DESCRIPTIONS = {
  gomoku: "下一颗棋，也猜一猜她的心思",
  aeroplane: "掷出好运，一起飞向终点",
  landlord: "三人牌局，后续支持 AI 补位",
  jungle: "轻巧但有策略的双人棋局",
  chinese_chess: "慢慢想一招，认真下一局"
};

/** The lobby isolates entertainment from ordering and reads its catalog from the API. */
export default function GamesPage() {
  const [games, setGames] = useState(FALLBACK_GAMES);
  const [usingFallback, setUsingFallback] = useState(false);

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    getGames()
      .then((items) => {
        setGames(items?.length ? items : FALLBACK_GAMES);
        setUsingFallback(false);
      })
      .catch(() => {
        setGames(FALLBACK_GAMES);
        setUsingFallback(true);
      });
  });

  const dice = games.find((game) => game.type === "dice") || FALLBACK_GAMES[0];
  const upcomingGames = games.filter((game) => game.type !== "dice");

  return (
    <View className="page game-center-page">
      <View className="game-center-heading">
        <Text className="eyebrow">PLAY TOGETHER</Text>
        <Text>一起玩 ♥</Text>
        <Text>吃饭是主线，小游戏是属于两个人的轻松支线。</Text>
      </View>

      <View className="game-section-title"><Text>今日游戏</Text><Text>双人娱乐</Text></View>
      <View className="game-feature-card">
        <View className="game-feature-top">
          <View className="game-feature-icon"><Text>{dice.icon}</Text></View>
          <View><Text>{dice.name}</Text><Text>真实 3D 骰桌 · 单机练习或双人实时对战</Text></View>
          <Text>已开放</Text>
        </View>
        <View className="game-feature-actions">
          <View className="dice-game-entry" onClick={() => Taro.navigateTo({ url: "/pages/dice/index" })}><Text>单机练习</Text><Text>和 AI 先来一局</Text></View>
          <View className="online-game-entry" onClick={() => Taro.navigateTo({ url: "/pages/dice-online/index" })}><Text>双人房间</Text><Text>邀请女朋友加入</Text></View>
        </View>
      </View>

      <View className="game-section-title"><Text>更多游戏</Text><Text>沿用同一房间系统</Text></View>
      <View className="game-coming-grid">
        {upcomingGames.map((game) => (
          <View key={game.type} className={game.status === "available" ? "available" : ""}>
            <View><Text>{game.icon}</Text></View>
            <Text>{game.name}</Text>
            <Text>{GAME_DESCRIPTIONS[game.type] || "正在认真准备"}</Text>
            <Text>{game.status === "available" ? "可以开始" : "即将上线"}</Text>
          </View>
        ))}
      </View>

      <View className="game-section-title"><Text>轻松决定</Text><Text>不建立在线房间</Text></View>
      <View className="game-wheel-card wheel-game-entry" onClick={() => Taro.navigateTo({ url: "/pages/wheel/index" })}>
        <View><Text>转</Text></View>
        <View><Text>今晚转盘</Text><Text>自己写选项，把纠结交给一点好运</Text></View>
        <Text>›</Text>
      </View>

      {usingFallback && <Text className="game-center-fallback">游戏目录暂时离线，已显示本地安全目录。</Text>}
      <View className="game-center-note"><Text>游戏房间只负责实时互动，不会修改点菜、订单和评价数据。</Text></View>
    </View>
  );
}
