import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { offersFixture, policyFixture } from "@/test/fixtures/gate-fixtures";
import { OfferList } from "./offer-list";

describe("OfferList", () => {
  it("renders the real backend-provided offers, price, and shelf-life facts", () => {
    render(<OfferList offers={offersFixture} policy={policyFixture} />);

    expect(screen.getByText(offersFixture[0].title_fa)).toBeInTheDocument();
    expect(screen.getByText(offersFixture[1].title_fa)).toBeInTheDocument();
    expect(
      screen.getAllByText(/کشور تامین‌کننده: فرانسه/).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: offersFixture[0].title_fa }),
    ).toHaveAttribute("href", `/shop/offer/${offersFixture[0].id}`);
  });

  it("shows an empty state, not a blank grid, when no offers are returned", () => {
    render(<OfferList offers={[]} policy={policyFixture} />);

    expect(
      screen.getByText("محصولی برای نمایش وجود ندارد"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/کشور تامین‌کننده/)).not.toBeInTheDocument();
  });
});
