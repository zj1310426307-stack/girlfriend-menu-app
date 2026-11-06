export default defineAppConfig({
  lazyCodeLoading: "requiredComponents",
  pages: [
    "pages/index/index",
    "pages/menu/index",
    "pages/my-orders/index",
    "pages/games/index",
    "pages/couple/index"
  ],
  subPackages: [
    // 情侣中心二级页：非 tabBar 页面，移出主包减少启动体积
    {
      root: "pages/couple/sub",
      pages: ["score", "records", "achievements", "game-records", "tasks", "timeline"]
    },
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
  // 分包预下载：高频跳转分包提前拉取，消除跳转等待
  preloadRule: {
    // 首页是冷启动第一页，详情与点菜车是最高频下一步，全网络预下载
    "pages/index/index": { network: "all", packages: ["pages/detail", "pages/cart"] },
    // 菜单页大概率进详情
    "pages/menu/index": { network: "all", packages: ["pages/detail"] },
    // 点菜单 tab 大概率进订单详情
    "pages/my-orders/index": { network: "all", packages: ["pages/order-detail"] },
    // 情侣中心二级页较小，全网络预下载
    "pages/couple/index": { network: "all", packages: ["pages/couple/sub"] },
    // 游戏分包体积较大，仅 WiFi 下预下载核心对战玩法
    "pages/games/index": {
      network: "wifi",
      packages: [
        "pages/games/gomoku",
        "pages/games/landlord",
        "pages/games/chess",
        "pages/games/animal",
        "pages/games/flight",
        "pages/dice",
        "pages/dice-online"
      ]
    }
  },
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
