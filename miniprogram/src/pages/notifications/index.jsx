import { useCallback, useState } from "react";
import Taro, { useDidShow, usePullDownRefresh } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { getNotifications, markNotificationRead } from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

const ICONS = { ORDER_STATUS: "餐", GAME_JOINED: "邀", GAME_STARTED: "玩", GAME_FINISHED: "局", ANNIVERSARY: "念" };

export default function NotificationsPage() {
  const customerId = getCustomerId();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!ensureInvitePassed()) return;
    setLoading(true);
    try { setItems(await getNotifications(customerId)); }
    catch (error) { Taro.showToast({ title: error.message || "消息加载失败", icon: "none" }); }
    finally { setLoading(false); Taro.stopPullDownRefresh(); }
  }, [customerId]);
  useDidShow(load);
  usePullDownRefresh(load);

  const open = async (item) => {
    if (!item.is_read) {
      await markNotificationRead(customerId, item.id).catch(() => null);
      setItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, is_read: true } : entry));
    }
    if (item.type === "ORDER_STATUS" && item.related_id) Taro.navigateTo({ url: `/pages/order-detail/index?id=${item.related_id}` });
    else if (item.type === "ANNIVERSARY") Taro.navigateTo({ url: "/pages/couple/timeline" });
    else if (item.type.startsWith("GAME_")) Taro.switchTab({ url: "/pages/games/index" });
  };

  return <View className="page notifications-page">
    <View className="notifications-head"><Text className="eyebrow">GENTLE REMINDERS</Text><Text>消息</Text><Text>只提醒真正重要的事：饭做好了、她加入房间了，还有快到的纪念日。</Text></View>
    {loading && <View className="notification-loading"><View /><View /><View /></View>}
    {!loading && items.length === 0 && <View className="notification-empty"><Text>现在很安静</Text><Text>有新的订单进度、游戏邀请或纪念日提醒时，会出现在这里。</Text></View>}
    <View className="notification-list">{items.map((item) => <View key={item.id} className={item.is_read ? "read" : "unread"} onClick={() => open(item)}><View><Text>{ICONS[item.type] || "信"}</Text>{!item.is_read && <Text />}</View><View><Text>{item.title}</Text><Text>{item.content}</Text><Text>{String(item.created_at).replace("T", " ").slice(0, 16)}</Text></View><Text>›</Text></View>)}</View>
  </View>;
}
