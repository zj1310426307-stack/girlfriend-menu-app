import { useCallback, useState } from "react";
import Taro, { useDidShow, usePullDownRefresh } from "@tarojs/taro";
import { Input, Picker, Text, Textarea, View } from "@tarojs/components";

import {
  createCoupleDate,
  createCoupleMemory,
  deleteCoupleDate,
  deleteCoupleMemory,
  getCoupleDates,
  getCoupleMemories
} from "../../api";
import { getCustomerId } from "../../utils/customer";
import { ensureInvitePassed } from "../../utils/invite";
import "./timeline.css";

const localDate = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

const TYPE_LABEL = {
  FIRST_MEAL: "第一顿饭", FIRST_COOK: "第一次下厨", TRAVEL: "旅行",
  GAME: "一起玩", ANNIVERSARY: "纪念日", OTHER: "生活"
};

export default function CoupleTimeline() {
  const customerId = getCustomerId();
  const [tab, setTab] = useState("memory");
  const [memories, setMemories] = useState([]);
  const [dates, setDates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [memoryForm, setMemoryForm] = useState({ title: "", content: "", event_date: localDate(), type: "OTHER", image_url: "" });
  const [dateForm, setDateForm] = useState({ title: "", date: localDate(), repeat_type: "YEARLY", reminder_days: 7 });

  const load = useCallback(async () => {
    if (!ensureInvitePassed()) return;
    setLoading(true);
    try {
      const [nextMemories, nextDates] = await Promise.all([
        getCoupleMemories(customerId), getCoupleDates(customerId)
      ]);
      setMemories(nextMemories || []);
      setDates(nextDates || []);
    } catch (error) {
      Taro.showToast({ title: error.message || "共同记录暂时加载失败", icon: "none" });
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [customerId]);

  useDidShow(load);
  usePullDownRefresh(load);

  const save = async () => {
    if (saving) return;
    const form = tab === "memory" ? memoryForm : dateForm;
    if (!form.title.trim()) return Taro.showToast({ title: "先写一个标题吧", icon: "none" });
    setSaving(true);
    try {
      if (tab === "memory") await createCoupleMemory(customerId, { ...memoryForm, title: memoryForm.title.trim(), content: memoryForm.content.trim() });
      else await createCoupleDate(customerId, { ...dateForm, title: dateForm.title.trim(), reminder_days: Number(dateForm.reminder_days) || 0 });
      setEditing(false);
      setMemoryForm({ title: "", content: "", event_date: localDate(), type: "OTHER", image_url: "" });
      setDateForm({ title: "", date: localDate(), repeat_type: "YEARLY", reminder_days: 7 });
      await load();
      Taro.showToast({ title: "已经存进我们的故事", icon: "success" });
    } catch (error) {
      Taro.showToast({ title: error.message || "保存失败", icon: "none" });
    } finally { setSaving(false); }
  };

  const remove = (kind, id) => Taro.showModal({ title: "删除这条记录？", content: "删除后不会影响订单、游戏和积分。" }).then(async ({ confirm }) => {
    if (!confirm) return;
    if (kind === "memory") await deleteCoupleMemory(customerId, id);
    else await deleteCoupleDate(customerId, id);
    load();
  });

  return (
    <View className="page timeline-page">
      <View className="timeline-hero"><Text className="eyebrow">OUR STORY</Text><Text>我们的时间轴</Text><Text>自动留下重要的第一次，也可以亲手写下旅行、纪念日和普通却珍贵的一天。</Text></View>
      <View className="timeline-tabs"><View className={tab === "memory" ? "active" : ""} onClick={() => setTab("memory")}><Text>共同记录</Text><Text>{memories.length}</Text></View><View className={tab === "date" ? "active" : ""} onClick={() => setTab("date")}><Text>纪念日</Text><Text>{dates.length}</Text></View></View>

      <View className="timeline-add" onClick={() => setEditing(!editing)}><Text>{editing ? "收起编辑" : tab === "memory" ? "＋ 写下一段共同记忆" : "＋ 添加一个纪念日"}</Text></View>
      {editing && <View className="timeline-form">
        <Text>{tab === "memory" ? "记录这一刻" : "记住这个日子"}</Text>
        <Input value={tab === "memory" ? memoryForm.title : dateForm.title} maxlength={100} placeholder="例如：第一次一起做番茄牛腩" onInput={(e) => tab === "memory" ? setMemoryForm({ ...memoryForm, title: e.detail.value }) : setDateForm({ ...dateForm, title: e.detail.value })} />
        {tab === "memory" ? <>
          <Picker mode="date" value={memoryForm.event_date} onChange={(e) => setMemoryForm({ ...memoryForm, event_date: e.detail.value })}><View className="timeline-picker"><Text>发生日期</Text><Text>{memoryForm.event_date} ›</Text></View></Picker>
          <Textarea value={memoryForm.content} maxlength={1000} placeholder="写一点当时的心情（可选）" onInput={(e) => setMemoryForm({ ...memoryForm, content: e.detail.value })} />
        </> : <>
          <Picker mode="date" value={dateForm.date} onChange={(e) => setDateForm({ ...dateForm, date: e.detail.value })}><View className="timeline-picker"><Text>纪念日期</Text><Text>{dateForm.date} ›</Text></View></Picker>
          <View className="timeline-repeat"><View className={dateForm.repeat_type === "YEARLY" ? "active" : ""} onClick={() => setDateForm({ ...dateForm, repeat_type: "YEARLY" })}><Text>每年提醒</Text></View><View className={dateForm.repeat_type === "NONE" ? "active" : ""} onClick={() => setDateForm({ ...dateForm, repeat_type: "NONE" })}><Text>只提醒一次</Text></View></View>
        </>}
        <View className="timeline-save" onClick={save}><Text>{saving ? "正在保存…" : "保存"}</Text></View>
      </View>}

      {loading && <View className="timeline-skeleton">{[1, 2, 3].map((item) => <View key={item} />)}</View>}
      {!loading && tab === "memory" && memories.length === 0 && <View className="timeline-empty"><Text>故事正在慢慢发生</Text><Text>完成第一单、第一顿饭或第一局游戏后，这里会自动亮起来。</Text></View>}
      {!loading && tab === "memory" && <View className="timeline-list">{memories.map((item) => <View key={item.id} className="timeline-item"><View><Text>{String(item.event_date).replaceAll("-", ".")}</Text><Text>{TYPE_LABEL[item.type] || "共同记忆"}</Text></View><View><Text>{item.title}</Text><Text>{item.content || "这一天值得被记住。"}</Text><Text onClick={() => remove("memory", item.id)}>删除</Text></View></View>)}</View>}
      {!loading && tab === "date" && dates.length === 0 && <View className="timeline-empty"><Text>还没有纪念日</Text><Text>加一个重要日子，到期前会在消息里温柔提醒。</Text></View>}
      {!loading && tab === "date" && <View className="date-list">{dates.map((item) => <View key={item.id}><View><Text>{String(item.date).slice(5).replace("-", ".")}</Text><Text>{item.repeat_type === "YEARLY" ? "每年" : "一次"}</Text></View><View><Text>{item.title}</Text><Text>提前 {item.reminder_days} 天提醒</Text></View><Text onClick={() => remove("date", item.id)}>删除</Text></View>)}</View>}
    </View>
  );
}
