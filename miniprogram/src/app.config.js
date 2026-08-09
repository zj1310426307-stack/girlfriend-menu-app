export default defineAppConfig({
  pages: [
    "pages/index/index",
    "pages/menu/index",
    "pages/my-orders/index",
    "pages/games/index",
    "pages/couple/index",
    "pages/couple/score",
    "pages/couple/records",
    "pages/couple/achievements",
    "pages/profile/index",
    "pages/wheel/index",
    "pages/dice/index",
    "pages/dice-online/index",
    "pages/admin-login/index",
    "pages/admin-dashboard/index",
    "pages/admin-orders/index",
    "pages/admin-dishes/index",
    "pages/admin-stats/index",
    "pages/detail/index",
    "pages/cart/index",
    "pages/order-detail/index"
  ],
  tabBar: {
    color: "#777d73",
    selectedColor: "#6f8469",
    backgroundColor: "#fffdf8",
    borderStyle: "white",
    list: [
      { pagePath: "pages/index/index", text: "首页" },
      { pagePath: "pages/menu/index", text: "菜单" },
      { pagePath: "pages/my-orders/index", text: "点菜单" },
      { pagePath: "pages/games/index", text: "一起玩" },
      { pagePath: "pages/couple/index", text: "我们" }
    ]
  },
  window: {
    backgroundTextStyle: "light",
    navigationBarBackgroundColor: "#fffaf7",
    navigationBarTitleText: "今天想吃什么呀",
    navigationBarTextStyle: "black",
    backgroundColor: "#faf7f2"
  }
});
