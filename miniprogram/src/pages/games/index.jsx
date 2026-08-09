import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import { createGameRoom, getGames } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed, INVITE_CODE } from "../../utils/invite";
import "./index.css";

const FALLBACK_GAMES = [
  { name: "大话骰", icon: "骰", type: "dice", status: "available" },
  { name: "五子棋", icon: "棋", type: "gomoku", status: "available" },
  { name: "飞行棋", icon: "飞", type: "aeroplane", status: "coming_soon" },
  { name: "斗地主", icon: "牌", type: "landlord", status: "coming_soon" },
  { name: "斗兽棋", icon: "兽", type: "jungle", status: "coming_soon" },
  { name: "中国象棋", icon: "象", type: "chinese_chess", status: "coming_soon" }
];

const GAME_DESCRIPTIONS = {
  aeroplane: "掷出好运，一起飞向终点",
  landlord: "三人牌局，后续支持 AI 补位",
  jungle: "轻巧但有策略的双人棋局",
  chinese_chess: "慢慢想一招，认真下一局"
};
const ROOM_CODE_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;

export default function GamesPage() {
  const [games, setGames] = useState(FALLBACK_GAMES);
  const [usingFallback, setUsingFallback] = useState(false);
  const [joinCode, setJoinCode] = useState("");
  const [creating, setCreating] = useState(false);

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
  const gomoku = { ...(games.find((game) => game.type === "gomoku") || FALLBACK_GAMES[1]), status: "available" };
  const upcomingGames = games.filter((game) => !["dice", "gomoku"].includes(game.type));
  const openGomoku = (roomCode = "", name = "") => Taro.navigateTo({
    url: `/pages/games/gomoku/index${roomCode ? `?room=${roomCode}${name ? `&name=${encodeURIComponent(name)}` : ""}` : ""}`
  });

  const createGomoku = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const room = await createGameRoom("gomoku", getCustomerId(), INVITE_CODE);
      openGomoku(room.room_code, "我");
    } catch (error) {
      Taro.showToast({ title: error.message || "创建房间失败", icon: "none" });
    } finally {
      setCreating(false);
    }
  };

  const joinGomoku = () => {
    const normalized = joinCode.trim().toUpperCase();
    if (!ROOM_CODE_PATTERN.test(normalized)) {
      Taro.showToast({ title: "请输入正确的 6 位房间码", icon: "none" });
      return;
    }
    openGomoku(normalized, "女朋友");
  };

  return (
    <View className="page game-center-page">
      <View className="game-center-heading">
        <Text className="eyebrow">PLAY TOGETHER</Text>
        <Text>一起玩 ♥</Text>
        <Text>认真吃饭，也认真陪彼此玩一会儿。</Text>
      </View>

      <View className="game-section-title"><Text>今日推荐</Text><Text>双人实时对战</Text></View>
      <View className="gomoku-feature-card">
        <View className="gomoku-feature-head">
          <View><Text>{gomoku.icon}</Text></View>
          <View><Text>{gomoku.name}</Text><Text>15×15 实时棋盘 · 五子连珠获胜</Text></View>
          <Text>新开放</Text>
        </View>
        <View className="gomoku-feature-line"><Text>●</Text><Text>○</Text><Text>●</Text><Text>○</Text><Text>●</Text></View>
        <View className="gomoku-feature-actions">
          <View className="gomoku-create" onClick={createGomoku}><Text>{creating ? "正在创建…" : "创建棋局"}</Text><Text>生成房间码邀请她</Text></View>
          <View className="gomoku-enter" onClick={() => openGomoku()}><Text>进入五子棋</Text><Text>查看规则与完整棋桌</Text></View>
        </View>
        <View className="gomoku-quick-join">
          <Input value={joinCode} maxlength={6} placeholder="输入 6 位房间码" onInput={(event) => setJoinCode(event.detail.value.toUpperCase())} onConfirm={joinGomoku} />
          <View onClick={joinGomoku}><Text>加入</Text></View>
        </View>
      </View>

      <View className="game-section-title"><Text>经典游戏</Text><Text>原有玩法完整保留</Text></View>
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

      <View className="game-section-title"><Text>轻松决定</Text><Text>不建立在线房间</Text></View>
      <View className="game-wheel-card wheel-game-entry" onClick={() => Taro.navigateTo({ url: "/pages/wheel/index" })}>
        <View><Text>转</Text></View>
        <View><Text>今晚转盘</Text><Text>自己写选项，把纠结交给一点好运</Text></View>
        <Text>›</Text>
      </View>

      <View className="game-section-title"><Text>更多游戏</Text><Text>沿用同一房间系统</Text></View>
      <View className="game-coming-grid">
        {upcomingGames.map((game) => (
          <View key={game.type}>
            <View><Text>{game.icon}</Text></View>
            <Text>{game.name}</Text>
            <Text>{GAME_DESCRIPTIONS[game.type] || "正在认真准备"}</Text>
            <Text>即将上线</Text>
          </View>
        ))}
      </View>

      {usingFallback && <Text className="game-center-fallback">游戏目录暂时离线，已显示本地安全目录。</Text>}
      <View className="game-center-note"><Text>在线棋局由服务器判断胜负并写入共同记录，点菜和订单流程不受影响。</Text></View>
    </View>
  );
}
