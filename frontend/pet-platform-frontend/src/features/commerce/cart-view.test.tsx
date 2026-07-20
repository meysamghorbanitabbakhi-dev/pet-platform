import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getOfferDetail } from "@/lib/api/client";
import { addCartItem } from "@/lib/cart";
import { offerDetailFixture } from "@/test/fixtures/gate-fixtures";
import { CartView } from "./cart-view";

vi.mock("@/lib/api/client", () => ({
  getOfferDetail: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("CartView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("shows an empty state with a link to the shop when the cart has no items", () => {
    renderWithQuery(<CartView />);

    expect(screen.getByText("سبد خرید خالی است")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "رفتن به فروشگاه" }),
    ).toHaveAttribute("href", "/shop");
    expect(getOfferDetail).not.toHaveBeenCalled();
  });

  it("re-fetches real offer data for cart items instead of trusting local pricing", async () => {
    addCartItem(offerDetailFixture.id);
    vi.mocked(getOfferDetail).mockResolvedValue(offerDetailFixture);

    renderWithQuery(<CartView />);

    expect(
      await screen.findByText(offerDetailFixture.title_fa),
    ).toBeInTheDocument();
    expect(getOfferDetail).toHaveBeenCalledWith(offerDetailFixture.id);
  });
});
