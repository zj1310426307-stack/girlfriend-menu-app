/** Create a compact action key reused by transport retries for one user intent. */
export function createGameActionId(prefix = "act") {
  const random = Math.random().toString(36).slice(2, 10);
  return `${prefix}_${Date.now().toString(36)}_${random}`;
}
