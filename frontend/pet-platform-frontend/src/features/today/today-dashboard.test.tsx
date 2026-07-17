import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  journeyOffersFixture,
  meContextFixture,
  policyDisabledFixture,
  policyFixture,
  returningTodayFixture,
  rexTodayFixture,
  unopenedTodayFixture,
} from "@/test/fixtures/gate-fixtures";
import { TodayDashboard } from "./today-dashboard";

describe("TodayDashboard", () => {
  it("renders setup status without a premature estimate before opening", () => {
    render(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={unopenedTodayFixture}
        journeyOffers={[]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
      />,
    );

    expect(screen.getByText(/هنوز باز شدن آن تایید نشده/)).toBeInTheDocument();
    expect(screen.queryByText(/۱۲ تا ۱۸ روز/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "تایید باز شدن بسته" }),
    ).toHaveAttribute(
      "href",
      `/inventory/${unopenedTodayFixture.food.state === "unopened" ? unopenedTodayFixture.food.inventory_unit_id : ""}`,
    );
  });

  it("keeps household inventory separate from pet consumption", () => {
    render(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={returningTodayFixture}
        journeyOffers={journeyOffersFixture}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
      />,
    );

    const boundary = screen.getByTestId("inventory-boundary");
    expect(within(boundary).getByText("انبار خانوار")).toBeInTheDocument();
    expect(within(boundary).getByText("مصرف پت")).toBeInTheDocument();
  });

  it("switches active pets through accessible tabs and arrow keys", async () => {
    const user = userEvent.setup();
    const onPetSelect = vi.fn();
    render(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={rexTodayFixture}
        journeyOffers={[]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={onPetSelect}
      />,
    );

    await user.click(screen.getByRole("tab", { name: /رکس/ }));
    expect(onPetSelect).toHaveBeenCalledWith(meContextFixture.pets[1].id);

    screen.getByRole("tab", { name: /بیشی/ }).focus();
    await user.keyboard("{ArrowLeft}");
    expect(onPetSelect).toHaveBeenCalledWith(meContextFixture.pets[1].id);
  });

  it("fails closed for care journeys and reserve-now", () => {
    render(
      <TodayDashboard
        context={meContextFixture}
        policy={policyDisabledFixture}
        today={returningTodayFixture}
        journeyOffers={journeyOffersFixture}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
      />,
    );

    expect(screen.queryByTestId("care-journeys")).not.toBeInTheDocument();
    expect(screen.queryByText(/رزرو اکنون/)).not.toBeInTheDocument();
  });

  it("keeps Garden free of score, purchase, streak, or decay mechanics", () => {
    const { container } = render(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={returningTodayFixture}
        journeyOffers={[]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
      />,
    );

    expect(screen.getByTestId("garden-preview")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(
      /XP|امتیاز|سلامت|خرید|استریک|افت/,
    );
  });
});
