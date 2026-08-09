import { ScrollView, Text, View } from "@tarojs/components";

import "./MoveHistory.css";

/** Present recent moves without taking ownership of game actions. */
export default function MoveHistory({ moves = [], names = {} }) {
  return (
    <View className="move-history-card">
      <View><Text>棋谱</Text><Text>{moves.length} 步</Text></View>
      <ScrollView scrollY className="move-history-list">
        {moves.length ? moves.slice().reverse().map((move) => (
          <View key={move.number}><Text>{move.number}</Text><Text>{names[move.player_id] || (move.player_id?.startsWith("ai_") ? "AI" : "玩家")}</Text><Text>{move.notation}</Text>{move.check && <Text>将</Text>}</View>
        )) : <Text className="move-history-empty">落子后，这里会保存每一步。</Text>}
      </ScrollView>
    </View>
  );
}
