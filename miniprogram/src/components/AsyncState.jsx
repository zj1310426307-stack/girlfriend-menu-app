import { Text, View } from "@tarojs/components";

export default function AsyncState({ type = "loading", message, onRetry }) {
  const labels = {
    loading: "正在准备，请稍等…",
    empty: "这里暂时还没有内容",
    error: "加载没有成功，请稍后重试"
  };
  return (
    <View className={`state-box ${type === "error" ? "error" : ""}`} onClick={onRetry}>
      <Text>{message || labels[type]}</Text>
      {type === "error" && onRetry && <Text className="muted">点这里重新加载</Text>}
    </View>
  );
}
