import { useCallback, useState } from "react";
import Taro, { useDidShow, usePullDownRefresh } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getMyGameRecords } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import { formatDate } from "./helpers";
import "./game-records.css";

const GAME_NAMES = { dice: "大话骰", gomoku: "五子棋", aeroplane: "飞行棋" };

function normalizeResponse(payload, customerId) {
  const records = Array.isArray(payload) ? payload : payload?.records || payload?.items || [];
  const wins = records.filter((record) => {
    const winner = record.winner_id || record.winner || record.result?.winner_id;
    return winner === customerId;
  }).length;
  return {
    records,
    total: payload?.total_games ?? payload?.total ?? records.length,
    wins: payload?.wins ?? payload?.win_count ?? wins,
    gomoku: payload?.gomoku_games ?? records.filter((record) => record.game_type === "gomoku").length
  };
}

function durationText(seconds) {
  const duration = Number(seconds || 0);
  if (!duration) return "轻松一局";
  if (duration < 60) return `${duration} 秒`;
  return `${Math.floor(duration / 60)} 分 ${duration % 60} 秒`;
}

export default function CoupleGameRecordsPage() {
  const [data, setData] = useState({ records: [], total: 0, wins: 0, gomoku: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!ensureInvitePassed()) return;
    setLoading(true);
    try {
      const customerId = getCustomerId();
      const response = await getMyGameRecords(customerId);
      setData(normalizeResponse(response, customerId));
      setError("");
    } catch (requestError) {
      setError(requestError.message || "游戏记录暂时没有连接");
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, []);

  useDidShow(load);
  usePullDownRefresh(load);

  return (
    <View className="page game-records-page">
      <View className="couple-subhead"><Text className="eyebrow">PLAY MEMORIES</Text><Text>我们的游戏记录</Text><Text>输赢会过去，一起认真玩过的时间会留下来。</Text></View>
      <View className="game-record-summary">
        <View><Text>{data.total}</Text><Text>一起玩过</Text></View>
        <View><Text>{data.wins}</Text><Text>我的胜局</Text></View>
        <View><Text>{data.gomoku}</Text><Text>五子棋局</Text></View>
      </View>

      {loading && <View className="game-record-state"><Text>正在翻开我们的游戏档案…</Text></View>}
      {!loading && error && <View className="game-record-state error" onClick={load}><Text>{error}</Text><Text>点这里重试</Text></View>}
      {!loading && !error && data.records.length === 0 && (
        <View className="game-record-empty">
          <Text>还没有一起玩过</Text><Text>去游戏大厅创建一局五子棋吧。</Text>
          <View onClick={() => Taro.switchTab({ url: "/pages/games/index" })}><Text>去一起玩</Text></View>
        </View>
      )}

      {!loading && !error && data.records.length > 0 && (
        <View className="game-record-list">
          <View className="game-record-heading"><Text>最近对局</Text><Text>{data.records.length} 条记录</Text></View>
          {data.records.map((record, index) => {
            const customerId = getCustomerId();
            const winnerId = record.winner_id || record.winner || record.result?.winner_id;
            const draw = record.result?.draw || !winnerId;
            const won = winnerId === customerId;
            return (
              <View className="game-record-row" key={record.id || `${record.game_type}-${index}`}>
                <View className={`game-record-icon ${record.game_type}`}><Text>{record.game_type === "gomoku" ? "棋" : "骰"}</Text></View>
                <View className="game-record-main">
                  <View><Text>{GAME_NAMES[record.game_type] || record.game_type || "双人游戏"}</Text><Text className={won ? "won" : ""}>{draw ? "和局" : won ? "胜利" : "参与"}</Text></View>
                  <Text>{durationText(record.duration)} · {formatDate(record.created_at)}</Text>
                  <Text>{record.description || (record.game_type === "gomoku" ? "完成一局五子棋对战" : "完成一局情侣游戏")}</Text>
                </View>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}
