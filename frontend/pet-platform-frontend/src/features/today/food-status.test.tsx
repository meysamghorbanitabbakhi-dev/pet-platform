import { describe, expect, it } from "vitest";
import {
  incomingTodayFixture,
  policyFixture,
  returningTodayFixture,
  unopenedTodayFixture,
} from "@/lib/fixtures/gate-fixtures";
import { foodStatusText } from "./food-status";

describe("Today food status", () => {
  it("does not show a remaining-days estimate for incoming orders", () => {
    expect(
      foodStatusText(incomingTodayFixture.food, policyFixture),
    ).not.toContain("روز");
  });

  it("does not show a remaining-days estimate before confirmed bag opening", () => {
    expect(
      foodStatusText(unopenedTodayFixture.food, policyFixture),
    ).not.toContain("روز");
  });

  it("shows backend-provided ranges only for estimated food", () => {
    expect(foodStatusText(returningTodayFixture.food, policyFixture)).toContain(
      "۱۲ تا ۱۸ روز",
    );
  });
});
