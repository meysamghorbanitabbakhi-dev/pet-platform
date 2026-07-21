import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getJourneyOffers,
  getMeContext,
  getPolicies,
  getToday,
} from "@/lib/api/client";
import {
  meContextFixture,
  policyFixture,
  rexTodayFixture,
} from "@/test/fixtures/gate-fixtures";
import { TodayExperience } from "./today-experience";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/today",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getJourneyOffers: vi.fn(),
  getMeContext: vi.fn(),
  getPolicies: vi.fn(),
  getToday: vi.fn(),
  listReplenishmentReservations: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("TodayExperience", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getToday).mockResolvedValue(rexTodayFixture);
    vi.mocked(getJourneyOffers).mockResolvedValue([]);
  });

  it("shows a full-page error state with retry when the policy/context call fails, not a partial or blank page", async () => {
    vi.mocked(getMeContext).mockRejectedValue(new Error("network"));
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);

    renderWithQuery(<TodayExperience />);

    expect(await screen.findByText("خطا در دریافت امروز")).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
  });

  it("retries both the policy and context calls from the error state's retry action", async () => {
    vi.mocked(getMeContext).mockRejectedValueOnce(new Error("network"));
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
    const user = userEvent.setup();

    renderWithQuery(<TodayExperience />);
    await screen.findByText("خطا در دریافت امروز");

    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));

    await waitFor(() =>
      expect(screen.queryByText("خطا در دریافت امروز")).not.toBeInTheDocument(),
    );
    expect(getMeContext).toHaveBeenCalledTimes(2);
  });
});
