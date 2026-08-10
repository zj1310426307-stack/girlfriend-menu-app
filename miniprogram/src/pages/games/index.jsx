import { useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Input, Text, View } from "@tarojs/components";

import { createGameRoom, getActiveGames, getGames } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const FALLBACK_GAMES = [
  { name: "大话骰", icon: "骰", type: "dice", status: "available" },
  { name: "五子棋", icon: "棋", type: "gomoku", status: "available" },
  { name: "飞行棋", icon: "飞", type: "aeroplane", status: "available" },
  { name: "斗地主", icon: "牌", type: "landlord", status: "available" },
  { name: "斗兽棋", icon: "兽", type: "jungle", status: "available" },
  { name: "中国象棋", icon: "象", type: "chinese_chess", status: "coming_soon" }
];

const GAME_DESCRIPTIONS = {
  aeroplane: "情侣房间或人机练习，一起飞向终点",
  landlord: "情侣牌桌或你与两个 AI，服务端洗牌",
  jungle: "标准 7×9 森林棋盘，支持 AI",
  chinese_chess: "慢慢想一招，认真下一局"
};
const ROOM_CODE_PATTERN = /^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/;

export default function GamesPage() {
  const [games, setGames] = useState(FALLBACK_GAMES);
  const [usingFallback, setUsingFallback] = useState(false);
  const [joinCode, setJoinCode] = useState("");
  const [creating, setCreating] = useState(false);
  const [activeGames, setActiveGames] = useState([]);

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
    getActiveGames(getCustomerId()).then(setActiveGames).catch(() => setActiveGames([]));
  });

  const continueGame = (game) => {
    const route = {
      dice: "/pages/dice-online/index",
      gomoku: "/pages/games/gomoku/index",
      aeroplane: "/pages/games/flight/index",
      landlord: "/pages/games/landlord/index",
      jungle: "/pages/games/animal/index",
      chinese_chess: "/pages/games/chess/index"
    }[game.game_type];
    if (route) Taro.navigateTo({ url: `${route}?room=${game.room_code}` });
  };

  const dice = games.find((game) => game.type === "dice") || FALLBACK_GAMES[0];
  const gomoku = { ...(games.find((game) => game.type === "gomoku") || FALLBACK_GAMES[1]), status: "available" };
  const flight = { ...(games.find((game) => game.type === "aeroplane") || FALLBACK_GAMES[2]), status: "available" };
  const landlord = { ...(games.find((game) => game.type === "landlord") || FALLBACK_GAMES[3]), status: "available" };
  const animal = { ...(games.find((game) => game.type === "jungle") || FALLBACK_GAMES[4]), status: "available" };
  const chess = { ...(games.find((game) => game.type === "chinese_chess") || FALLBACK_GAMES[5]), status: "available" };
  const upcomingGames = games.filter((game) => !["dice", "gomoku", "aeroplane", "landlord", "jungle", "chinese_chess"].includes(game.type));
  const openGomoku = (roomCode = "", name = "") => Taro.navigateTo({
    url: `/pages/games/gomoku/index${roomCode ? `?room=${roomCode}${name ? `&name=${encodeURIComponent(name)}` : ""}` : ""}`
  });

  const createGomoku = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const room = await createGameRoom("gomoku", getCustomerId(), "");
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

      {activeGames.length > 0 && <>
        <View className="game-section-title"><Text>继续游戏</Text><Text>断开后也能找回来</Text></View>
        <View className="continue-game-list">{activeGames.map((game) => <View key={game.room_code} onClick={() => continueGame(game)}><View><Text>{({ dice: "骰", gomoku: "棋", aeroplane: "飞", landlord: "牌", jungle: "兽", chinese_chess: "象" })[game.game_type] || "玩"}</Text></View><View><Text>{({ dice: "大话骰", gomoku: "五子棋", aeroplane: "飞行棋", landlord: "斗地主", jungle: "斗兽棋", chinese_chess: "中国象棋" })[game.game_type] || game.game_type}</Text><Text>房间 {game.room_code} · {game.status === "playing" ? "进行中" : "等待加入"}</Text></View><Text>继续 ›</Text></View>)}</View>
      </>}

      <View className="game-section-title"><Text>今日推荐</Text><Text>双人实时 · 人机练习</Text></View>
      <View className="gomoku-feature-card">
        <View className="gomoku-feature-head">
          <View><Text>{gomoku.icon}</Text></View>
          <View><Text>{gomoku.name}</Text><Text>15×15 实时棋盘 · 支持聪明 AI 陪练</Text></View>
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

      <View className="game-section-title"><Text>情侣飞行棋</Text><Text>任务与随机互动</Text></View>
      <View className="flight-feature-card" onClick={() => Taro.navigateTo({ url: "/pages/games/flight/index" })}>
        <View className="flight-feature-copy">
          <View><Text>{flight.icon}</Text></View>
          <View><Text>{flight.name}</Text><Text>情侣或人机 · 服务端掷骰 · 互动格加默契</Text></View>
          <Text>V2.4</Text>
        </View>
        <View className="flight-mini-route">
          {["起", "♥", "餐", "乐", "挑", "终"].map((item, index) => <View key={`${item}-${index}`} className={item === "♥" ? "love" : ""}><Text>{item}</Text></View>)}
        </View>
        <View className="flight-feature-action"><Text>创建或加入飞行棋房间</Text><Text>›</Text></View>
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

      <View className="game-section-title"><Text>V2.5 新牌桌</Text><Text>统一状态与 AI 陪玩</Text></View>
      <View className="v25-game-grid">
        <View className="landlord-entry" onClick={() => Taro.navigateTo({ url: "/pages/games/landlord/index" })}>
          <View><Text>{landlord.icon}</Text><Text>AI×2</Text></View>
          <Text>{landlord.name}</Text>
          <Text>情侣双排或单人挑战两个 AI。手牌私密，服务器判定。</Text>
          <Text>进入牌桌 ›</Text>
        </View>
        <View className="animal-entry" onClick={() => Taro.navigateTo({ url: "/pages/games/animal/index" })}>
          <View><Text>{animal.icon}</Text><Text>7×9</Text></View>
          <Text>{animal.name}</Text>
          <Text>情侣房间或单人 AI，狮虎跳河、占领兽穴。</Text>
          <Text>进入森林 ›</Text>
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
        <View className="chess-feature-card" onClick={() => Taro.navigateTo({ url: "/pages/games/chess/index" })}>
          <View><Text>{chess.icon || "象"}</Text><Text>将</Text></View>
          <View><Text>{chess.name || "中国象棋"}</Text><Text>标准棋盘、服务端判定、AI 陪练与完整棋谱。</Text><Text>进入象棋 →</Text></View>
        </View>
        <View className="game-data-card" onClick={() => Taro.navigateTo({ url: "/pages/games/ranking/index" })}>
          <View><Text>榜</Text></View><Text>游戏数据中心</Text><Text>战绩、胜率与本月默契榜</Text><Text>查看 →</Text>
        </View>
        <View className="game-data-card companion" onClick={() => Taro.navigateTo({ url: "/pages/games/ai/index" })}>
          <View><Text>伴</Text></View><Text>今日陪伴小结</Text><Text>真实记录生成，不猜测心情</Text><Text>查看 →</Text>
        </View>
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
