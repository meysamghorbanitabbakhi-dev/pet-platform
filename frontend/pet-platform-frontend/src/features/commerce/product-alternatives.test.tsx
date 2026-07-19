import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listProductAlternatives } from "@/lib/api/client";
import {
  policyFixture,
  productAlternativesFixture,
} from "@/test/fixtures/gate-fixtures";
import { ProductAlternatives } from "./product-alternatives";

vi.mock("@/lib/api/client", () => ({
  listProductAlternatives: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("ProductAlternatives", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("labels alternatives as platform-curated, not a clinical substitute", async () => {
    vi.mocked(listProductAlternatives).mockResolvedValue(
      productAlternativesFixture,
    );

    renderWithQuery(
      <ProductAlternatives productId="product-1" policy={policyFixture} />,
    );

    expect(
      await screen.findByText(productAlternativesFixture[0].offer.title_fa),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/نه جایگزین تضمین‌شده بالینی یا تغذیه‌ای/),
    ).toBeInTheDocument();
  });

  it("shows an empty state when the operator has approved no alternatives", async () => {
    vi.mocked(listProductAlternatives).mockResolvedValue([]);

    renderWithQuery(
      <ProductAlternatives productId="product-1" policy={policyFixture} />,
    );

    expect(
      await screen.findByText("در حال حاضر جایگزینی ثبت نشده است"),
    ).toBeInTheDocument();
  });

  it("shows an error state and recovers via retry", async () => {
    vi.mocked(listProductAlternatives).mockRejectedValue(
      new Error("network down"),
    );
    const user = userEvent.setup();

    renderWithQuery(
      <ProductAlternatives productId="product-1" policy={policyFixture} />,
    );

    expect(
      await screen.findByText("جایگزین‌ها دریافت نشد"),
    ).toBeInTheDocument();

    vi.mocked(listProductAlternatives).mockResolvedValue(
      productAlternativesFixture,
    );
    await user.click(screen.getByRole("button", { name: "تلاش مجدد" }));

    expect(
      await screen.findByText(productAlternativesFixture[0].offer.title_fa),
    ).toBeInTheDocument();
  });

  it("links to the alternative offer's own detail page", async () => {
    vi.mocked(listProductAlternatives).mockResolvedValue(
      productAlternativesFixture,
    );

    renderWithQuery(
      <ProductAlternatives productId="product-1" policy={policyFixture} />,
    );

    const link = await screen.findByRole("link", {
      name: productAlternativesFixture[0].offer.title_fa,
    });
    expect(link).toHaveAttribute(
      "href",
      `/shop/offer/${productAlternativesFixture[0].offer.id}`,
    );
  });
});
