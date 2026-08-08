import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const GAMES = [
  { key: "wheel", title: "今晚转盘", desc: "自己写选项，把纠结交给一点好运", mark: "转", url: "/pages/wheel/index", tone: "sage" },
  { key: "dice", title: "3D 大话骰", desc: "酒吧桌面、上滑开盅和 AI 对局", mark: "骰", url: "/pages/dice/index", tone: "dark" },
  { key: "online", title: "和女朋友实时对战", desc: "创建双人房间，实时叫骰和计分", mark: "双", url: "/pages/dice-online/index", tone: "coral" }
];

/** Keeps entertainment separate from the food ordering conversion path. */
export default function GamesPage() {
  useDidShow(() => ensureInvitePassed());
  return (
    <View className="page v2-games-page">
      <View className="v2-games-heading"><Text className="eyebrow">PLAY TOGETHER</Text><Text>一起玩一会儿</Text><Text>决定不了的事交给转盘，吃饱以后再开一局。</Text></View>
      <View className="v2-game-list">
        {GAMES.map((game) => (
          <View key={game.url} className={`v2-game-card ${game.tone} ${game.key}-game-entry`} onClick={() => Taro.navigateTo({ url: game.url })}>
            <View><Text>{game.mark}</Text></View>
            <View><Text>{game.title}</Text><Text>{game.desc}</Text></View>
            <Text>›</Text>
          </View>
        ))}
      </View>
      <View className="v2-game-note"><Text>小游戏只记录本地设置或临时房间状态，不会改变订单和评价数据。</Text></View>
    </View>
  );
}
