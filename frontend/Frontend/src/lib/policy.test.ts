import { describe, expect, it } from "vitest";
import {
  journeyOffersFixture,
  policyDisabledFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import {
  enabled,
  isPolicyCompatible,
  shouldRenderCareJourneys,
  shouldRenderReserveNow,
} from "./policy";

describe("runtime policy gates", () => {
  it("fails closed when policy is absent", () => {
    expect(enabled(undefined, "care_journey_delivery_enabled")).toBe(false);
    expect(shouldRenderCareJourneys(undefined, journeyOffersFixture)).toBe(
      false,
    );
    expect(shouldRenderReserveNow(undefined)).toBe(false);
  });

  it("keeps required policy invariants explicit", () => {
    expect(isPolicyCompatible(policyFixture)).toBe(true);
    expect(policyFixture.delivery_commitment_hours).toBe(366);
    expect(policyFixture.reserve_now_enabled).toBe(false);
    expect(policyFixture.full_payment_only).toBe(true);
  });

  it("hides care journeys when runtime policy disables them", () => {
    expect(
      shouldRenderCareJourneys(policyDisabledFixture, journeyOffersFixture),
    ).toBe(false);
    expect(shouldRenderCareJourneys(policyFixture, journeyOffersFixture)).toBe(
      true,
    );
  });
});
