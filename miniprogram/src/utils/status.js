export const ORDER_STEPS = ["待接单", "已接单", "制作中", "已完成"];

export const STATUS_TEXT = {
  待接单: "我还没看到，稍等一下",
  已接单: "收到，马上安排",
  制作中: "正在为你准备",
  已完成: "可以开吃啦",
  暂时做不了: "这道菜今天可能安排不了"
};

export function reviewHint(order) {
  if (order.status === "已完成" && order.has_review) return "已评价";
  if (order.status === "已完成") return "可以评价啦";
  return "做好后可评价";
}

export function formatTime(value) {
  if (!value) return "";
  return String(value).replace("T", " ").slice(0, 16);
}
