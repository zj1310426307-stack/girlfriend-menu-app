import { useMemo, useState } from "react";
import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getActiveGames, getGames } from "../../api";
import { ROUTES } from "../../config/routes";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const GAME_CATALOG = [
  {
    type: "gomoku",
    icon: "五",
    name: "五子棋",
    description: "15×15 标准棋盘，落子清楚，适合随时来一局。",
    route: ROUTES.GOMOKU,
    tone: "ink",
    modes: "双人 · 人机"
  },
  {
    type: "aeroplane",
    icon: "飞",
    name: "飞行棋",
    description: "服务器掷骰，四枚棋子与情侣互动事件。",
    route: ROUTES.FLIGHT,
    tone: "sky",
    modes: "双人 · 人机"
  },
  {
    type: "landlord",
    icon: "牌",
    name: "斗地主",
    description: "横屏牌桌，提示、合法牌型和胜负都由服务器判断。",
    route: ROUTES.LANDLORD,
    tone: "amber",
    modes: "双人+AI · 人机"
  },
  {
    type: "jungle",
    icon: "兽",
    name: "斗兽棋",
    description: "标准 7×9 棋盘，河流、陷阱和兽穴规则完整。",
    route: ROUTES.ANIMAL,
    tone: "forest",
    modes: "双人 · 人机"
  },
  {
    type: "chinese_chess",
    icon: "象",
    name: "中国象棋",
    description: "服务端校验走法，棋谱保存，断线后可以继续。",
    route: ROUTES.CHESS,
    tone: "clay",
    modes: "双人 · 人机"
  },
  {
    type: "dice",
    icon: "骰",
    name: "大话骰",
    description: "自己的骰子只自己可见，开盅后再公开结果。",
    route: ROUTES.DICE,
    onlineRoute: ROUTES.DICE_ONLINE,
    tone: "night",
    modes: "单机 · 双人"
  }
];

const GAME_BY_TYPE = Object.fromEntries(GAME_CATALOG.map((game) => [game.type, game]));

/** A calm, data-driven hub. Room creation belongs to each game, not this page. */
export default function GamesPage() {
  const [serverGames, setServerGames] = useState([]);
  const [activeGames, setActiveGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const load = async () => {
    setLoading(true);
    const customerId = getCustomerId();
    const [catalogResult, activeResult] = await Promise.all([
      getGames().then((value) => ({ ok: true, value })).catch((error) => ({ ok: false, error })),
      getActiveGames(customerId).then((value) => ({ ok: true, value })).catch((error) => ({ ok: false, error }))
    ]);
    if (catalogResult.ok) {
      setServerGames(catalogResult.value || []);
      setOffline(false);
    } else {
      setOffline(true);
    }
    setActiveGames(activeResult.ok ? activeResult.value || [] : []);
    setLoading(false);
  };

  useDidShow(() => {
    if (!ensureInvitePassed()) return;
    load();
  });

  const games = useMemo(() => GAME_CATALOG.map((game) => {
    const remote = serverGames.find((item) => item.type === game.type);
    return { ...game, status: remote?.status || "available" };
  }), [serverGames]);

  const openGame = (game, online = false) => {
    if (game.status !== "available") {
      Taro.showToast({ title: "这个游戏正在维护，请稍后再来", icon: "none" });
      return;
    }
    Taro.navigateTo({ url: online && game.onlineRoute ? game.onlineRoute : game.route });
  };

  const continueGame = (room) => {
    const game = GAME_BY_TYPE[room.game_type];
    if (!game) return;
    Taro.navigateTo({
      url: `${game.type === "dice" ? game.onlineRoute : game.route}?room=${room.room_code}&resume=1`
    });
  };

  return (
    <View className="page game-center-page">
      <View className="game-center-heading">
        <Text className="eyebrow">PLAY TOGETHER</Text>
        <Text>一起玩</Text>
        <Text>选一个现在就想玩的。双人房间和人机练习都放在各自游戏里，不再让首页替你做决定。</Text>
      </View>

      {activeGames.length > 0 && (
        <View className="game-continue-section">
          <View className="game-section-title">
            <Text>继续上次</Text>
            <Text>{activeGames.length} 个未结束房间</Text>
          </View>
          <View className="continue-game-list">
            {activeGames.slice(0, 4).map((room) => {
              const game = GAME_BY_TYPE[room.game_type] || { icon: "玩", name: room.game_type };
              return (
                <View key={room.room_code} className="continue-game-card" onClick={() => continueGame(room)}>
                  <View className={`continue-game-icon tone-${game.tone || "ink"}`}><Text>{game.icon}</Text></View>
                  <View className="continue-game-copy">
                    <Text>{game.name}</Text>
                    <Text>房间 {room.room_code} · {room.status === "playing" ? "进行中" : "等待加入"}</Text>
                  </View>
                  <View className="continue-game-action"><Text>继续</Text></View>
                </View>
              );
            })}
          </View>
        </View>
      )}

      <View className="game-section-title game-library-title">
        <Text>选择游戏</Text>
        <Text>{loading ? "正在同步…" : "6 个长期玩法"}</Text>
      </View>
      <View className="game-library-grid v25-game-grid">
        {games.map((game) => (
          <View
            key={game.type}
            className={`game-tile tone-${game.tone} ${game.type === "gomoku" ? "gomoku-feature-card" : ""} ${game.type === "landlord" ? "landlord-entry" : ""} ${game.type === "jungle" ? "animal-entry" : ""} ${game.type === "chinese_chess" ? "chess-feature-card" : ""}`}
            onClick={() => openGame(game)}
          >
            <View className="game-tile-top">
              <View className="game-tile-icon"><Text>{game.icon}</Text></View>
              <Text className="game-tile-mode">{game.modes}</Text>
            </View>
            <Text className="game-tile-name">{game.name}</Text>
            <Text className="game-tile-description">{game.description}</Text>
            {game.onlineRoute ? (
              <View className="game-tile-actions">
                <View onClick={(event) => { event.stopPropagation?.(); openGame(game); }}><Text>单机练习</Text></View>
                <View onClick={(event) => { event.stopPropagation?.(); openGame(game, true); }}><Text>双人房间</Text></View>
              </View>
            ) : (
              <View className="game-tile-enter"><Text>进入游戏</Text><Text>›</Text></View>
            )}
          </View>
        ))}
      </View>

      <View className="game-section-title">
        <Text>轻松一下</Text>
        <Text>不占用在线房间</Text>
      </View>
      <View className="game-tool-list">
        <View onClick={() => Taro.navigateTo({ url: ROUTES.WHEEL })}>
          <View className="game-tool-icon coral"><Text>转</Text></View>
          <View><Text>今晚转盘</Text><Text>自定义选项，帮你们结束纠结</Text></View><Text>›</Text>
        </View>
        <View className="game-data-card" onClick={() => Taro.navigateTo({ url: ROUTES.GAME_RANKING })}>
          <View className="game-tool-icon green"><Text>榜</Text></View>
          <View><Text>游戏记录</Text><Text>查看局数、胜率和共同回忆</Text></View><Text>›</Text>
        </View>
        <View onClick={() => Taro.navigateTo({ url: ROUTES.GAME_AI })}>
          <View className="game-tool-icon amber"><Text>伴</Text></View>
          <View><Text>今日小结</Text><Text>根据真实记录生成，不猜测心情</Text></View><Text>›</Text>
        </View>
      </View>

      {offline && (
        <View className="game-offline-card" onClick={load}>
          <Text>游戏目录暂时没有连上服务器</Text>
          <Text>已显示本地安全目录，点这里重新同步</Text>
        </View>
      )}
      <View className="game-center-note">
        <Text>规则、随机数和胜负由服务器确认；网络波动时不会偷偷改结果，恢复连接后可继续未完成的房间。</Text>
      </View>
    </View>
  );
}
