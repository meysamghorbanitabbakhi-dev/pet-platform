"use client";

const storageKey = "pet-platform.auth-return";
// Every real protected route, matching src/app's top-level route
// directories -- an explicit allowlist, never an open redirect. /breeds is
// deliberately excluded: it is public and never triggers a session-expiry
// redirect in the first place.
const allowedPrefixes = [
  "/account",
  "/cart",
  "/checkout",
  "/diary",
  "/garden",
  "/inventory",
  "/journeys",
  "/notifications",
  "/orders",
  "/pets",
  "/privacy",
  "/shop",
  "/support",
  "/today",
];

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
