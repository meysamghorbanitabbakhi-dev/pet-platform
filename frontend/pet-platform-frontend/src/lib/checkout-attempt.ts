"use client";

const storageKey = "pet-platform.checkout-attempt.v1";
const latestOrderKey = "pet-platform.latest-order-id";

type CheckoutAttempt = {
  orderId?: string;
  orderKey: string;
  paymentKey?: string;
  paymentOrderId?: string;
  signature: string;
  version: 1;
};

function randomKey(prefix: string) {
  const value =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${value}`;
}

function readAttempt(): CheckoutAttempt | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(
      window.localStorage.getItem(storageKey) ?? "null",
    );
    if (
      parsed &&
      parsed.version === 1 &&
      typeof parsed.signature === "string" &&
      typeof parsed.orderKey === "string"
    ) {
      return parsed as CheckoutAttempt;
    }
  } catch {
    return null;
  }
  return null;
}

function writeAttempt(attempt: CheckoutAttempt) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey, JSON.stringify(attempt));
}

export function getOrderAttempt(signature: string) {
  const existing = readAttempt();
  if (existing?.signature === signature) return existing;
  const next: CheckoutAttempt = {
    orderKey: randomKey("checkout"),
    signature,
    version: 1,
  };
  writeAttempt(next);
  return next;
}

export function markOrderCreated(signature: string, orderId: string) {
  const attempt = getOrderAttempt(signature);
  const next = { ...attempt, orderId };
  writeAttempt(next);
  setLatestOrderId(orderId);
  return next;
}

export function getPaymentAttempt(orderId: string) {
  const existing = readAttempt();
  const next: CheckoutAttempt =
    existing?.orderId === orderId
      ? existing
      : {
          orderId,
          orderKey: randomKey("checkout"),
          signature: `order:${orderId}`,
          version: 1,
        };
  if (next.paymentOrderId !== orderId || !next.paymentKey) {
    const updated = {
      ...next,
      paymentKey: randomKey("payment"),
      paymentOrderId: orderId,
    };
    writeAttempt(updated);
    return updated;
  }
  writeAttempt(next);
  return next;
}

export function setLatestOrderId(orderId: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(latestOrderKey, orderId);
}

export function getLatestOrderId() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(latestOrderKey);
}

export function clearCheckoutAttempt() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(storageKey);
}
