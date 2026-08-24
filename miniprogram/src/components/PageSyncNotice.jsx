import { Text, View } from "@tarojs/components";

import "./PageSyncNotice.css";

/** Keep cached page content visible while communicating refresh or retry state. */
export default function PageSyncNotice({ loading, offline, onRetry }) {
  if (loading) {
    return <View className="page-sync-notice"><Text>正在同步最新内容…</Text></View>;
  }
  if (offline) {
    return (
      <View className="page-sync-notice is-offline" onClick={onRetry}>
        <Text>当前显示上次内容，点这里重新同步</Text>
      </View>
    );
  }
  return null;
}
