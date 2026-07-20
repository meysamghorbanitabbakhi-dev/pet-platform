import {
  act,
  render,
  renderHook,
  screen,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  journeyOffersFixture,
  meContextFixture,
  policyDisabledFixture,
  policyFixture,
  replenishmentReservationFixture,
  returningTodayFixture,
  rexTodayFixture,
  unopenedTodayFixture,
} from "@/test/fixtures/gate-fixtures";
import { selectedPetStorageKey } from "@/lib/selected-pet";
import { TodayDashboard, usePersistedSelectedPet } from "./today-dashboard";

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

  it("shows a pending replenishment reservations banner only when the runtime policy enables it", () => {
    const { rerender } = render(
      <TodayDashboard
        context={meContextFixture}
        policy={{ ...policyFixture, replenishment_reservation_enabled: true }}
        today={returningTodayFixture}
        journeyOffers={[]}
        replenishmentReservations={[replenishmentReservationFixture]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
      />,
    );

    const banner = screen.getByTestId("replenishment-reservations-banner");
    expect(
      within(banner).getByText("۱ پیشنهاد در انتظار تایید شما"),
    ).toBeInTheDocument();
    expect(banner).toHaveAttribute("href", "/inventory");

    rerender(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={returningTodayFixture}
        journeyOffers={[]}
        replenishmentReservations={[replenishmentReservationFixture]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
      />,
    );
    expect(
      screen.queryByTestId("replenishment-reservations-banner"),
    ).not.toBeInTheDocument();
  });

  it("hides the replenishment reservations banner once nothing is pending anymore", () => {
    render(
      <TodayDashboard
        context={meContextFixture}
        policy={{ ...policyFixture, replenishment_reservation_enabled: true }}
        today={returningTodayFixture}
        journeyOffers={[]}
        replenishmentReservations={[
          { ...replenishmentReservationFixture, status: "approved" },
        ]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
      />,
    );

    expect(
      screen.queryByTestId("replenishment-reservations-banner"),
    ).not.toBeInTheDocument();
  });

  it("shows a distinct empty state when the household itself hasn't been created yet", () => {
    render(
      <TodayDashboard
        context={{
          ...meContextFixture,
          onboarding: { ...meContextFixture.onboarding, needs_household: true },
          pets: [],
        }}
        policy={policyFixture}
        today={null}
        journeyOffers={[]}
        activePetId=""
        onPetSelect={() => {}}
      />,
    );

    expect(screen.getByText("هنوز خانواری ثبت نشده است")).toBeInTheDocument();
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

  it("shows a background-revalidation indicator distinct from the initial-load skeleton", () => {
    const { rerender } = render(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={returningTodayFixture}
        journeyOffers={[]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
        refreshing={false}
      />,
    );
    expect(screen.queryByText("در حال به‌روزرسانی")).not.toBeInTheDocument();

    rerender(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={returningTodayFixture}
        journeyOffers={[]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
        refreshing
      />,
    );
    expect(screen.getByText("در حال به‌روزرسانی")).toBeInTheDocument();
  });

  it("warns when the previously-selected pet is no longer available, naming the pet now shown", async () => {
    const user = userEvent.setup();
    const onAcknowledgePetReset = vi.fn();
    render(
      <TodayDashboard
        context={meContextFixture}
        policy={policyFixture}
        today={returningTodayFixture}
        journeyOffers={[]}
        activePetId={meContextFixture.pets[0].id}
        onPetSelect={() => {}}
        petWasReset
        onAcknowledgePetReset={onAcknowledgePetReset}
      />,
    );

    const banner = screen
      .getByText(/پتی که پیش‌تر مشاهده می‌کردید دیگر در دسترس نیست/)
      .closest(".banner");
    expect(banner).not.toBeNull();
    expect(
      within(banner as HTMLElement).getByText(
        new RegExp(meContextFixture.pets[0].name),
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "متوجه شدم" }));
    expect(onAcknowledgePetReset).toHaveBeenCalled();
  });
});

describe("usePersistedSelectedPet", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("silently falls back to the first pet when nothing is stored yet", () => {
    const { result } = renderHook(() =>
      usePersistedSelectedPet(meContextFixture),
    );

    expect(result.current.activePetId).toBe(meContextFixture.pets[0].id);
    expect(result.current.petWasReset).toBe(false);
  });

  it("surfaces, rather than silently swallows, a stored pet id that no longer exists", () => {
    window.localStorage.setItem(selectedPetStorageKey, "deleted-pet-id");

    const { result } = renderHook(() =>
      usePersistedSelectedPet(meContextFixture),
    );

    expect(result.current.activePetId).toBe(meContextFixture.pets[0].id);
    expect(result.current.petWasReset).toBe(true);
  });

  it("clears the reset notice once the user acknowledges it or picks a pet themselves", () => {
    window.localStorage.setItem(selectedPetStorageKey, "deleted-pet-id");
    const { result } = renderHook(() =>
      usePersistedSelectedPet(meContextFixture),
    );
    expect(result.current.petWasReset).toBe(true);

    act(() => result.current.acknowledgePetReset());

    expect(result.current.petWasReset).toBe(false);
  });

  it("does not raise the reset notice when a real pet is already correctly selected", () => {
    window.localStorage.setItem(
      selectedPetStorageKey,
      meContextFixture.pets[1].id,
    );

    const { result } = renderHook(() =>
      usePersistedSelectedPet(meContextFixture),
    );

    expect(result.current.activePetId).toBe(meContextFixture.pets[1].id);
    expect(result.current.petWasReset).toBe(false);
  });
});
