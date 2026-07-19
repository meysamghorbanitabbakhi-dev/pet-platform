import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getPolicies, searchOffers } from "@/lib/api/client";
import {
  offerSearchFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import { OfferSearch } from "./offer-search";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/shop/search",
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/api/client", () => ({
  getPolicies: vi.fn(),
  searchOffers: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("OfferSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
  });

  it("shows a prompt state before any query is entered, without calling search", () => {
    renderWithQuery(<OfferSearch />);

    expect(screen.getByText("عبارتی برای جستجو وارد کنید")).toBeInTheDocument();
    expect(searchOffers).not.toHaveBeenCalled();
  });

  it("debounces typing instead of searching on every keystroke", async () => {
    vi.mocked(searchOffers).mockResolvedValue(offerSearchFixture);
    const user = userEvent.setup();

    renderWithQuery(<OfferSearch />);
    await user.type(screen.getByLabelText("جستجو در فروشگاه"), "رویال");

    expect(searchOffers).not.toHaveBeenCalled();

    await waitFor(() => expect(searchOffers).toHaveBeenCalledWith("رویال"), {
      timeout: 2000,
    });
    expect(searchOffers).toHaveBeenCalledTimes(1);
  });

  it("supports keyboard (Enter) submission without waiting for debounce", async () => {
    vi.mocked(searchOffers).mockResolvedValue(offerSearchFixture);
    const user = userEvent.setup();

    renderWithQuery(<OfferSearch />);
    const input = screen.getByLabelText("جستجو در فروشگاه");
    await user.type(input, "رویال{Enter}");

    expect(
      await screen.findByText(offerSearchFixture.items[0].title_fa),
    ).toBeInTheDocument();
  });

  it("shows a query-specific empty state when nothing matches", async () => {
    vi.mocked(searchOffers).mockResolvedValue({
      items: [],
      page: { has_more: false, limit: 25, offset: 0, total: 0 },
    });
    const user = userEvent.setup();

    renderWithQuery(<OfferSearch />);
    await user.type(screen.getByLabelText("جستجو در فروشگاه"), "zzz{Enter}");

    expect(await screen.findByText("نتیجه‌ای یافت نشد")).toBeInTheDocument();
  });

  it("shows an error state with a retry action on search failure", async () => {
    vi.mocked(searchOffers).mockRejectedValue(new Error("network down"));
    const user = userEvent.setup();

    renderWithQuery(<OfferSearch />);
    await user.type(screen.getByLabelText("جستجو در فروشگاه"), "test{Enter}");

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("جستجو ناموفق بود")).toBeInTheDocument();
    expect(
      within(alert).getByRole("button", { name: "تلاش مجدد" }),
    ).toBeInTheDocument();
  });

  it("preserves the query in the URL", async () => {
    vi.mocked(searchOffers).mockResolvedValue(offerSearchFixture);
    const user = userEvent.setup();

    renderWithQuery(<OfferSearch />);
    await user.type(screen.getByLabelText("جستجو در فروشگاه"), "test{Enter}");

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/shop/search?q=test", {
        scroll: false,
      }),
    );
  });

  it("announces the result count for screen readers", async () => {
    vi.mocked(searchOffers).mockResolvedValue(offerSearchFixture);
    const user = userEvent.setup();

    renderWithQuery(<OfferSearch />);
    await user.type(screen.getByLabelText("جستجو در فروشگاه"), "test{Enter}");

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        `${offerSearchFixture.page.total} نتیجه یافت شد`,
      ),
    );
  });
});
