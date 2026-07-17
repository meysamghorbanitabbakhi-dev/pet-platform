import { describe, expect, it } from "vitest";
import type { MeContextResponse } from "@/lib/api-types";
import { meContextFixture } from "@/test/fixtures/gate-fixtures";
import { routeFromMeContext } from "./onboarding-routing";

function contextWith(
  onboarding: MeContextResponse["onboarding"],
): MeContextResponse {
  return { ...meContextFixture, onboarding };
}

describe("routeFromMeContext", () => {
  it("routes missing household, pet, address and complete onboarding", () => {
    expect(
      routeFromMeContext(
        contextWith({
          needs_address: true,
          needs_household: true,
          needs_pet: true,
        }),
      ),
    ).toBe("/onboarding/household");
    expect(
      routeFromMeContext(
        contextWith({
          needs_address: true,
          needs_household: false,
          needs_pet: true,
        }),
      ),
    ).toBe("/onboarding/pet");
    expect(
      routeFromMeContext(
        contextWith({
          needs_address: true,
          needs_household: false,
          needs_pet: false,
        }),
      ),
    ).toBe("/onboarding/address");
    expect(
      routeFromMeContext(
        contextWith({
          needs_address: false,
          needs_household: false,
          needs_pet: false,
        }),
      ),
    ).toBe("/today");
  });
});
