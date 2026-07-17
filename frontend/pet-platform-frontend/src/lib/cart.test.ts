import { beforeEach, describe, expect, it } from "vitest";
import { addCartItem, cartSignature, readCart, setCartQuantity } from "./cart";
import {
  getOrderAttempt,
  getPaymentAttempt,
  markOrderCreated,
} from "./checkout-attempt";

describe("T10 local cart and idempotency stores", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("stores only offer IDs and quantities in the versioned cart", () => {
    addCartItem("offer-1");
    setCartQuantity("offer-1", 3);

    const raw = window.localStorage.getItem("pet-platform.cart.v1");
    expect(raw).toContain("offer-1");
    expect(raw).toContain("quantity");
    expect(raw).not.toMatch(/price|irr|تومان|supplier|entity/i);
    expect(readCart().items).toEqual([{ offerId: "offer-1", quantity: 3 }]);
  });

  it("keeps stable checkout and payment idempotency keys for the same attempt", () => {
    addCartItem("offer-1");
    const signature = cartSignature(readCart(), "household-1:address-1");

    const first = getOrderAttempt(signature);
    const second = getOrderAttempt(signature);
    expect(second.orderKey).toBe(first.orderKey);

    markOrderCreated(signature, "order-1");
    const firstPayment = getPaymentAttempt("order-1");
    const secondPayment = getPaymentAttempt("order-1");
    expect(secondPayment.paymentKey).toBe(firstPayment.paymentKey);
  });
});
