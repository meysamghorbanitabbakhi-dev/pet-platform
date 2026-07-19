import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getOfferDetail, getPolicies } from "@/lib/api/client";
import { toggleCompareItem } from "@/lib/compare-list";
import {
  catOfferDetailFixture,
  offerDetailFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import { OfferCompare } from "./offer-compare";

vi.mock("@/lib/api/client", () => ({
  getOfferDetail: vi.fn(),
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

describe("OfferCompare", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
  });

  it("shows an empty state, not a one-item comparison, when nothing else has been added yet", () => {
    renderWithQuery(<OfferCompare offerId={offerDetailFixture.id} />);

    expect(
      screen.getByText("محصولی برای مقایسه انتخاب نشده است"),
    ).toBeInTheDocument();
    expect(getOfferDetail).not.toHaveBeenCalled();
  });

  it("renders the current offer alongside the ones already added, fetched from the real backend", async () => {
    toggleCompareItem(catOfferDetailFixture.id);
    vi.mocked(getOfferDetail).mockImplementation((id: string) =>
      Promise.resolve(
        id === offerDetailFixture.id
          ? offerDetailFixture
          : catOfferDetailFixture,
      ),
    );

    renderWithQuery(<OfferCompare offerId={offerDetailFixture.id} />);

    expect(
      await screen.findByText(offerDetailFixture.title_fa),
    ).toBeInTheDocument();
    expect(
      screen.getByText(catOfferDetailFixture.title_fa),
    ).toBeInTheDocument();
    expect(getOfferDetail).toHaveBeenCalledWith(offerDetailFixture.id);
    expect(getOfferDetail).toHaveBeenCalledWith(catOfferDetailFixture.id);
  });

  it("removes an offer from the comparison through the real local store, not just the view", async () => {
    toggleCompareItem(catOfferDetailFixture.id);
    vi.mocked(getOfferDetail).mockImplementation((id: string) =>
      Promise.resolve(
        id === offerDetailFixture.id
          ? offerDetailFixture
          : catOfferDetailFixture,
      ),
    );
    const user = userEvent.setup();

    renderWithQuery(<OfferCompare offerId={offerDetailFixture.id} />);
    await screen.findByText(catOfferDetailFixture.title_fa);

    await user.click(screen.getByRole("button", { name: "حذف از مقایسه" }));

    await waitFor(() =>
      expect(
        screen.getByText("محصولی برای مقایسه انتخاب نشده است"),
      ).toBeInTheDocument(),
    );
  });
});
