export default defineAppConfig({
  lazyCodeLoading: "requiredComponents",
  pages: [
    "pages/index/index",
    "pages/menu/index",
    "pages/my-orders/index",
    "pages/games/index",
    "pages/couple/index",
    "pages/couple/score",
    "pages/couple/records",
    "pages/couple/achievements",
    "pages/couple/game-records",
    "pages/couple/tasks",
    "pages/couple/timeline"
  ],
  subPackages: [
    { root: "pages/detail", pages: ["index"] },
    { root: "pages/cart", pages: ["index"] },
    { root: "pages/order-detail", pages: ["index"] },
    { root: "pages/notifications", pages: ["index"] },
    { root: "pages/profile", pages: ["index"] },
    { root: "pages/games/gomoku", pages: ["index"] },
    { root: "pages/games/flight", pages: ["index"] },
    { root: "pages/games/landlord", pages: ["index"] },
    { root: "pages/games/animal", pages: ["index"] },
    { root: "pages/games/chess", pages: ["index"] },
    { root: "pages/games/ranking", pages: ["index"] },
    { root: "pages/games/ai", pages: ["index"] },
    { root: "pages/wheel", pages: ["index"] },
    { root: "pages/dice", pages: ["index"] },
    { root: "pages/dice-online", pages: ["index"] },
    { root: "pages/admin-login", pages: ["index"] },
    { root: "pages/admin-dashboard", pages: ["index"] },
    { root: "pages/admin-orders", pages: ["index"] },
    { root: "pages/admin-dishes", pages: ["index"] },
    { root: "pages/admin-stats", pages: ["index"] }
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
