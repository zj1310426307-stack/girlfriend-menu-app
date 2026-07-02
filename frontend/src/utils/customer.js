const CUSTOMER_ID_KEY = "gf_customer_id";

export function getCustomerId() {
  const existing = localStorage.getItem(CUSTOMER_ID_KEY);
  if (existing) return existing;

  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 12);
  const customerId = `gf_${timestamp}_${random}`;
  localStorage.setItem(CUSTOMER_ID_KEY, customerId);
  return customerId;
}
