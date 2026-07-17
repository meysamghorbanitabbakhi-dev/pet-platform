"use client";

const storageKey = "pet-platform.auth-return";
const allowedPrefixes = ["/cart", "/checkout", "/shop", "/orders"];

export function safeReturnTo(value: string | null | undefined) {
  if (!value || !value.startsWith("/")) return null;
  if (value.startsWith("//")) return null;
  return allowedPrefixes.some(
    (prefix) => value === prefix || value.startsWith(`${prefix}/`),
  )
    ? value
    : null;
}

export function storeReturnTo(value: string | null | undefined) {
  const safe = safeReturnTo(value);
  if (typeof window === "undefined" || !safe) return;
  window.localStorage.setItem(storageKey, safe);
}

export function consumeReturnTo() {
  if (typeof window === "undefined") return null;
  const safe = safeReturnTo(window.localStorage.getItem(storageKey));
  window.localStorage.removeItem(storageKey);
  return safe;
}
