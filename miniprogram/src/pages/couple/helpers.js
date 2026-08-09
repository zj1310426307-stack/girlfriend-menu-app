export const EMPTY_COUPLE_SCORE = {
  total: 0,
  level: "初识",
  month_score: 0,
  points_total: 0,
  next_level_at: 50,
  progress: 0,
  month_meals: 0,
  month_games: 0,
  month_encouragement: 0,
  breakdown: {
    recent_interaction: 0,
    shared_experience: 0,
    satisfaction_feedback: 0
  }
};

export function formatDate(value) {
  if (!value) return "还没有记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function dateLabel(value) {
  const date = new Date(value);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (left, right) => left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate();
  if (sameDay(date, today)) return "今天";
  if (sameDay(date, yesterday)) return "昨天";
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}
