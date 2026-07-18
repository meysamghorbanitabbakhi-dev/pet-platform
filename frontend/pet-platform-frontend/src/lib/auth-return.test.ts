import { beforeEach, describe, expect, it } from "vitest";
import { consumeReturnTo, safeReturnTo, storeReturnTo } from "./auth-return";

describe("safeReturnTo", () => {
  it("accepts every real protected route prefix", () => {
    for (const path of [
      "/account",
      "/cart",
      "/checkout/address",
      "/diary",
      "/garden/pet-1",
      "/inventory/unit-1",
      "/journeys/active/journey-1",
      "/notifications",
      "/orders/order-1",
      "/pets/pet-1",
      "/privacy",
      "/shop/offer/offer-1",
      "/support/request-1",
      "/today",
    ]) {
      expect(safeReturnTo(path)).toBe(path);
    }
  });

  it("preserves a query string on an allowed path", () => {
    expect(safeReturnTo("/inventory/unit-1?tab=details")).toBe(
      "/inventory/unit-1?tab=details",
    );
  });

  it("rejects a path with no allowlisted prefix", () => {
    expect(safeReturnTo("/auth/mobile")).toBeNull();
    expect(safeReturnTo("/onboarding/household")).toBeNull();
  });

  it("rejects a protocol-relative URL, never allowing an open redirect off-site", () => {
    expect(safeReturnTo("//evil.example.com")).toBeNull();
  });

  it("rejects an absolute URL", () => {
    expect(safeReturnTo("https://evil.example.com/today")).toBeNull();
  });

  it("rejects null/empty input", () => {
    expect(safeReturnTo(null)).toBeNull();
    expect(safeReturnTo(undefined)).toBeNull();
    expect(safeReturnTo("")).toBeNull();
  });
});

describe("storeReturnTo / consumeReturnTo", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("round-trips a safe value and consumes it exactly once", () => {
    storeReturnTo("/inventory/unit-1");
    expect(consumeReturnTo()).toBe("/inventory/unit-1");
    expect(consumeReturnTo()).toBeNull();
  });

  it("never stores an unsafe value", () => {
    storeReturnTo("https://evil.example.com");
    expect(consumeReturnTo()).toBeNull();
  });
});
