import { useState } from "react";
import Taro from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { createCoupleMemory } from "../api";
import { getCustomerId } from "../utils/customer";
import "./GameMemoryButton.css";

const localDate = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

/**
 * One-tap "save this match into our story" action for finished games.
 *
 * Writes a GAME-type couple memory through the existing timeline API, so the
 * record shows up in 我们 -> 我们的故事 with the 一起玩 label and stays
 * deletable there like any hand-written memory.
 */
export default function GameMemoryButton({ title, content, sourceType = "" }) {
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (saved || busy) return;
    if (!title || !content) return;
    setBusy(true);
    try {
      await createCoupleMemory(getCustomerId(), {
        type: "GAME",
        title: title.trim(),
        content: content.trim(),
        event_date: localDate(),
        ...(sourceType ? { source_type: String(sourceType).slice(0, 50) } : {})
      });
      setSaved(true);
      Taro.showToast({ title: "已存进我们的故事 ♥", icon: "success" });
    } catch (error) {
      Taro.showToast({ title: error?.message || "保存失败，稍后再试", icon: "none" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <View className={`game-memory-button ${saved ? "saved" : ""} ${busy ? "busy" : ""}`} onClick={save}>
      <Text>{saved ? "已存进我们的故事 ♥" : busy ? "正在保存…" : "把这一刻存进我们的故事"}</Text>
    </View>
  );
}
