import { describe, expect, it } from "vitest";
import { notificationDestinationHref } from "./notification-destination";

describe("notificationDestinationHref", () => {
  it("maps each known kind to its real allowlisted route", () => {
    expect(notificationDestinationHref({ id: "order-1", kind: "order" })).toBe(
      "/orders/order-1",
    );
    expect(
      notificationDestinationHref({ id: "unit-1", kind: "inventory_unit" }),
    ).toBe("/inventory/unit-1");
    expect(
      notificationDestinationHref({ id: "journey-1", kind: "journey" }),
    ).toBe("/journeys/active/journey-1");
    expect(
      notificationDestinationHref({
        id: "request-1",
        kind: "customer_request",
      }),
    ).toBe("/support/request-1");
    expect(notificationDestinationHref({ id: "offer-1", kind: "offer" })).toBe(
      "/shop/offer/offer-1",
    );
  });

  it("never produces a link for kind=none, even with a stray id", () => {
    expect(notificationDestinationHref({ id: null, kind: "none" })).toBeNull();
  });

  it("never produces a link when id is null, regardless of kind", () => {
    expect(notificationDestinationHref({ id: null, kind: "order" })).toBeNull();
  });
});
