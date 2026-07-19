import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  incomingTodayFixture,
  policyFixture,
  returningTodayFixture,
  unopenedTodayFixture,
} from "@/test/fixtures/gate-fixtures";
import { foodStatusText, NextEventCard } from "./food-status";

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

  it("links an active-journey attention to the real active journey page, not a dead-end label", () => {
    render(
      <NextEventCard
        today={{
          ...returningTodayFixture,
          primary_attention: { journey_id: "journey-42", type: "active_journey" },
        }}
      />,
    );
    expect(
      screen.getByRole("link", { name: /یک مسیر مراقبتی فعال دارید/ }),
    ).toHaveAttribute("href", "/journeys/active/journey-42");
  });
});
