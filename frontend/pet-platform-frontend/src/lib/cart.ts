"use client";

export const cartStorageKey = "pet-platform.cart.v1";
const cartEvent = "pet-platform-cart-change";

export type CartItem = {
  offerId: string;
  quantity: number;
};

export type CartState = {
  items: CartItem[];
  updatedAt: string;
  version: 1;
};

const emptyCart: CartState = {
  items: [],
  updatedAt: "",
  version: 1,
};

function nowIso() {
  return new Date().toISOString();
}

function normalizeQuantity(quantity: number) {
  if (!Number.isFinite(quantity)) return 1;
  return Math.min(100, Math.max(1, Math.trunc(quantity)));
}

function normalizeCart(value: unknown): CartState {
  if (
    !value ||
    typeof value !== "object" ||
    !("version" in value) ||
    value.version !== 1 ||
    !Array.isArray((value as CartState).items)
  ) {
    return { ...emptyCart };
  }

  const items = (value as CartState).items
    .filter(
      (item) =>
        item &&
        typeof item.offerId === "string" &&
        typeof item.quantity === "number",
    )
    .map((item) => ({
      offerId: item.offerId,
      quantity: normalizeQuantity(item.quantity),
    }));

  return {
    items,
    updatedAt:
      typeof (value as CartState).updatedAt === "string"
        ? (value as CartState).updatedAt
        : "",
    version: 1,
  };
}

export function readCart(): CartState {
  if (typeof window === "undefined") return { ...emptyCart };
  try {
    return normalizeCart(
      JSON.parse(window.localStorage.getItem(cartStorageKey) ?? "{}"),
    );
  } catch {
    return { ...emptyCart };
  }
}

export function writeCart(cart: CartState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(cartStorageKey, JSON.stringify(cart));
  window.dispatchEvent(new Event(cartEvent));
}

export function clearCart() {
  writeCart({ ...emptyCart, updatedAt: nowIso() });
}

export function addCartItem(offerId: string, quantity = 1) {
  const cart = readCart();
  const existing = cart.items.find((item) => item.offerId === offerId);
  const nextItems = existing
    ? cart.items.map((item) =>
        item.offerId === offerId
          ? {
              ...item,
              quantity: normalizeQuantity(item.quantity + quantity),
            }
          : item,
      )
    : [...cart.items, { offerId, quantity: normalizeQuantity(quantity) }];
  writeCart({ items: nextItems, updatedAt: nowIso(), version: 1 });
}

export function setCartQuantity(offerId: string, quantity: number) {
  const cart = readCart();
  const nextItems = cart.items
    .map((item) =>
      item.offerId === offerId
        ? { ...item, quantity: normalizeQuantity(quantity) }
        : item,
    )
    .filter((item) => item.quantity > 0);
  writeCart({ items: nextItems, updatedAt: nowIso(), version: 1 });
}

export function removeCartItem(offerId: string) {
  const cart = readCart();
  writeCart({
    items: cart.items.filter((item) => item.offerId !== offerId),
    updatedAt: nowIso(),
    version: 1,
  });
}

export function cartSignature(cart: CartState, context: string) {
  const items = [...cart.items].sort((a, b) =>
    a.offerId.localeCompare(b.offerId),
  );
  return JSON.stringify({ context, items, version: cart.version });
}

export function subscribeCart(listener: () => void) {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener(cartEvent, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(cartEvent, listener);
    window.removeEventListener("storage", listener);
  };
}
