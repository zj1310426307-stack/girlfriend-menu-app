import Taro from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { clearAdminToken } from "../utils/admin";
import "./AdminNav.css";

const ITEMS = [
  { key: "dashboard", label: "总览", url: "/pages/admin-dashboard/index" },
  { key: "orders", label: "订单", url: "/pages/admin-orders/index" },
  { key: "dishes", label: "菜品", url: "/pages/admin-dishes/index" },
  { key: "stats", label: "统计", url: "/pages/admin-stats/index" }
];

export default function AdminNav({ active }) {
  const navigate = (item) => {
    if (item.key === active) return;
    Taro.redirectTo({ url: item.url });
  };

  const logout = () => {
    clearAdminToken();
    Taro.reLaunch({ url: "/pages/admin-login/index" });
  };

  return (
    <View className="admin-nav-wrap">
      <View className="admin-nav">
        {ITEMS.map((item) => (
          <View
            key={item.key}
            className={`admin-nav-item ${active === item.key ? "is-active" : ""}`}
            onClick={() => navigate(item)}
          >
            <Text>{item.label}</Text>
          </View>
        ))}
        <View className="admin-nav-item admin-nav-logout" onClick={logout}>
          <Text>退出</Text>
        </View>
      </View>
    </View>
  );
}
