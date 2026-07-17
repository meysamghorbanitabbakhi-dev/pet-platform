"use client";

const storageKey = "pet-platform.checkout-selection.v1";

export type CheckoutSelection = {
  addressId: string;
  householdId: string;
  version: 1;
};

export function readCheckoutSelection(): CheckoutSelection | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(
      window.localStorage.getItem(storageKey) ?? "null",
    );
    if (
      parsed &&
      parsed.version === 1 &&
      typeof parsed.householdId === "string" &&
      typeof parsed.addressId === "string"
    ) {
      return parsed as CheckoutSelection;
    }
  } catch {
    return null;
  }
  return null;
}

export function writeCheckoutSelection(
  selection: Omit<CheckoutSelection, "version">,
) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    storageKey,
    JSON.stringify({ ...selection, version: 1 }),
  );
}
