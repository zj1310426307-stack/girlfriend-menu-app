export const ORDER_STEPS = ["待接单", "已接单", "制作中", "已完成"];
export const ACTIVE_ORDER_STATUSES = ["待接单", "已接单", "制作中"];

export const STATUS_TEXT = {
  待接单: "我还没看到，稍等一下",
  已接单: "收到，马上安排",
  制作中: "正在为你准备",
  已完成: "可以开吃啦",
  暂时做不了: "这道菜今天可能安排不了"
};

export const ORDER_HEADLINES = {
  待接单: "点菜已经送出去啦",
  已接单: "已经收到你的点菜啦",
  制作中: "正在认真为你准备",
  已完成: "可以开吃啦",
  暂时做不了: "这次可能要换一道啦"
};

/** Return a customer-facing headline that matches the current order state. */
export function orderHeadline(status) {
  return ORDER_HEADLINES[status] || "已经收到你的点菜啦";
}

/** Explain the review availability without promising completion for a closed order. */
export function reviewHint(order) {
  if (order.status === "已完成" && order.has_review) return "已评价";
  if (order.status === "已完成") return "可以评价啦";
  if (order.status === "暂时做不了") return "本次未制作";
  return "做好后可评价";
}

/** Format an API timestamp for compact customer-facing order cards. */
export function formatTime(value) {
  if (!value) return "";
  return String(value).replace("T", " ").slice(0, 16);
}
