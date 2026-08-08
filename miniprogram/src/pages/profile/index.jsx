import Taro, { useDidShow } from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { ensureInvitePassed } from "../../utils/invite";
import "./index.css";

/** Profile keeps personal tools and the low-emphasis kitchen admin entry. */
export default function ProfilePage() {
  useDidShow(() => ensureInvitePassed());
  return (
    <View className="page v2-profile-page">
      <View className="v2-profile-hero"><Text className="eyebrow">OUR LITTLE KITCHEN</Text><Text>关于我们的口味</Text><Text>收藏、点菜记录和小厨房设置都收在这里。</Text></View>
      <View className="v2-profile-grid">
        <View onClick={() => Taro.switchTab({ url: "/pages/my-orders/index" })}><Text>点菜记录</Text><Text>查看状态、历史与评价</Text></View>
        <View className="is-muted"><Text>收藏菜品</Text><Text>正在为 V2.0 准备</Text></View>
        <View className="is-muted"><Text>口味偏好</Text><Text>辣度与忌口后续可设置</Text></View>
        <View className="is-muted"><Text>饮食记忆</Text><Text>积累更多订单后生成</Text></View>
      </View>
      <View className="v2-profile-admin" onClick={() => Taro.navigateTo({ url: "/pages/admin-login/index" })}>
        <View><Text>小厨房管理</Text><Text>查看订单、维护菜单和统计</Text></View><Text>›</Text>
      </View>
      <Text className="v2-profile-note">管理功能需要单独输入管理密码。</Text>
    </View>
  );
}
