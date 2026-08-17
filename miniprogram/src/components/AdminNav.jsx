import Taro from "@tarojs/taro";
import { Text, View } from "@tarojs/components";

import { ROUTES } from "../config/routes";
import { clearAdminToken } from "../utils/admin";
import "./AdminNav.css";

const ITEMS = [
  { key: "dashboard", label: "总览", url: ROUTES.ADMIN_DASHBOARD },
  { key: "orders", label: "订单", url: ROUTES.ADMIN_ORDERS },
  { key: "dishes", label: "菜品", url: ROUTES.ADMIN_DISHES },
  { key: "stats", label: "统计", url: ROUTES.ADMIN_STATS }
];

export default function AdminNav({ active }) {
  const navigate = (item) => {
    if (item.key === active) return;
    Taro.redirectTo({ url: item.url });
  };

  const logout = () => {
    clearAdminToken();
    Taro.reLaunch({ url: ROUTES.ADMIN_LOGIN });
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
