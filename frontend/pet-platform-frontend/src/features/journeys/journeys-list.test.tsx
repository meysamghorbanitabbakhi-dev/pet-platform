import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getJourneyOffers, getMeContext, getPolicies } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  journeyOffersFixture,
  meContextFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import { JourneysList } from "./journeys-list";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/journeys",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getJourneyOffers: vi.fn(),
  getMeContext: vi.fn(),
  getPolicies: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("JourneysList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
  });

  it("shows only backend-approved journey offers for the active pet", async () => {
    vi.mocked(getJourneyOffers).mockResolvedValue(journeyOffersFixture);
    renderWithQuery(<JourneysList />);

    expect(
      await screen.findByText(journeyOffersFixture[0].title_fa),
    ).toBeInTheDocument();
    expect(getJourneyOffers).toHaveBeenCalledWith(meContextFixture.pets[0].id);
  });

  it("shows a policy-hidden empty state, not an error, when care journeys are disabled", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      care_journey_delivery_enabled: false,
    });
    renderWithQuery(<JourneysList />);

    expect(
      await screen.findByText("مسیرهای مراقبتی در دسترس نیست"),
    ).toBeInTheDocument();
    expect(getJourneyOffers).not.toHaveBeenCalled();
  });

  it("shows an empty state, not an error, when the pet has no eligible journeys", async () => {
    vi.mocked(getJourneyOffers).mockResolvedValue([]);
    renderWithQuery(<JourneysList />);

    expect(
      await screen.findByText("مسیر مراقبتی فعالی برای این پت وجود ندارد"),
    ).toBeInTheDocument();
  });

  it("redirects to the session-expired screen on a 401", async () => {
    vi.mocked(getMeContext).mockRejectedValue(new ApiError("expired", 401));
    renderWithQuery(<JourneysList />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/auth/session-expired"),
    );
  });

  it("shows a loading skeleton while journey offers are being fetched, not a blank screen", async () => {
    let resolveOffers: (value: typeof journeyOffersFixture) => void = () => {};
    vi.mocked(getJourneyOffers).mockReturnValue(
      new Promise((resolve) => {
        resolveOffers = resolve;
      }),
    );

    renderWithQuery(<JourneysList />);

    expect(
      (await screen.findAllByRole("status")).length,
    ).toBeGreaterThan(0);
    resolveOffers(journeyOffersFixture);
    expect(
      await screen.findByText(journeyOffersFixture[0].title_fa),
    ).toBeInTheDocument();
  });

  it("shows a dedicated error state with retry when journey offers fail to load", async () => {
    vi.mocked(getJourneyOffers).mockRejectedValue(new Error("network"));
    const user = userEvent.setup();

    renderWithQuery(<JourneysList />);

    expect(
      await screen.findByText("فهرست مسیرها در دسترس نیست"),
    ).toBeInTheDocument();
    vi.mocked(getJourneyOffers).mockResolvedValue(journeyOffersFixture);
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));

    expect(
      await screen.findByText(journeyOffersFixture[0].title_fa),
    ).toBeInTheDocument();
  });
});
