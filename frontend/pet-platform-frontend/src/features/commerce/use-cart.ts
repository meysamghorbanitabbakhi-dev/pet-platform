"use client";

import { useSyncExternalStore } from "react";
import { readCart, subscribeCart, type CartState } from "@/lib/cart";

const initialCart: CartState = {
  items: [],
  updatedAt: "",
  version: 1,
};

let cartSnapshot = initialCart;

function sameCart(left: CartState, right: CartState) {
  if (
    left.version !== right.version ||
    left.updatedAt !== right.updatedAt ||
    left.items.length !== right.items.length
  ) {
    return false;
  }

  return left.items.every((item, index) => {
    const other = right.items[index];
    return item.offerId === other?.offerId && item.quantity === other.quantity;
  });
}

function getCartSnapshot() {
  const next = readCart();
  if (sameCart(cartSnapshot, next)) return cartSnapshot;
  cartSnapshot = next;
  return cartSnapshot;
}

export function useCartSnapshot() {
  return useSyncExternalStore(
    subscribeCart,
    getCartSnapshot,
    () => initialCart,
  );
}
