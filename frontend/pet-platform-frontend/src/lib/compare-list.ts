"use client";

export const compareListStorageKey = "pet-platform.compare-list.v1";
const compareListEvent = "pet-platform-compare-list-change";

// A comparison is a small, user-picked set of offers viewed side by side --
// not an algorithmic "similar products" feature (that requires a
// substitutability rule the backend does not define yet, see G5-SHOP-13).
// Bounding it keeps the page a simple bounded-set view, not an open list.
export const MAX_COMPARE_ITEMS = 4;

function readIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed: unknown = JSON.parse(
      window.localStorage.getItem(compareListStorageKey) ?? "[]",
    );
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((id): id is string => typeof id === "string");
  } catch {
    return [];
  }
}

function writeIds(ids: string[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(compareListStorageKey, JSON.stringify(ids));
  window.dispatchEvent(new Event(compareListEvent));
}

export function readCompareList(): string[] {
  return readIds();
}

export function isInCompareList(offerId: string): boolean {
  return readIds().includes(offerId);
}

export function toggleCompareItem(offerId: string): void {
  const ids = readIds();
  if (ids.includes(offerId)) {
    writeIds(ids.filter((id) => id !== offerId));
    return;
  }
  if (ids.length >= MAX_COMPARE_ITEMS) return;
  writeIds([...ids, offerId]);
}

export function clearCompareList(): void {
  writeIds([]);
}

export function subscribeCompareList(listener: () => void) {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener(compareListEvent, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(compareListEvent, listener);
    window.removeEventListener("storage", listener);
  };
}
