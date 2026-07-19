import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  listAvailabilitySubscriptions,
  listProductAlternatives,
} from "@/lib/api/client";
import {
  offerDetailFixture,
  policyFixture,
  productAlternativesFixture,
  unavailableOfferFixture,
} from "@/test/fixtures/gate-fixtures";
import { OfferDetail } from "./offer-detail";

vi.mock("@/lib/api/client", () => ({
  cancelAvailabilitySubscription: vi.fn(),
  listAvailabilitySubscriptions: vi.fn(),
  listProductAlternatives: vi.fn(),
  subscribeAvailability: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("OfferDetail alternatives placement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listAvailabilitySubscriptions).mockResolvedValue({
      items: [],
      page: { has_more: false, limit: 25, offset: 0, total: 0 },
    });
  });

  it("does not render or fetch alternatives for an available offer", () => {
    renderWithQuery(
      <OfferDetail offer={offerDetailFixture} policy={policyFixture} />,
    );

    expect(
      screen.queryByText("جایگزین‌های پیشنهادی پلتفرم"),
    ).not.toBeInTheDocument();
    expect(listProductAlternatives).not.toHaveBeenCalled();
  });

  it("renders curated alternatives for an unavailable offer", async () => {
    vi.mocked(listProductAlternatives).mockResolvedValue(
      productAlternativesFixture,
    );

    renderWithQuery(
      <OfferDetail offer={unavailableOfferFixture} policy={policyFixture} />,
    );

    expect(screen.getByText("جایگزین‌های پیشنهادی پلتفرم")).toBeInTheDocument();
    await waitFor(() =>
      expect(listProductAlternatives).toHaveBeenCalledWith(
        unavailableOfferFixture.product_id,
      ),
    );
    expect(
      await screen.findByText(productAlternativesFixture[0].offer.title_fa),
    ).toBeInTheDocument();
  });
});
