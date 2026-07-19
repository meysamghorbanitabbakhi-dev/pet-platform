import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { MAX_COMPARE_ITEMS, toggleCompareItem } from "@/lib/compare-list";
import { CompareToggleButton } from "./compare-toggle-button";

describe("CompareToggleButton", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("adds the offer to the comparison list and reflects the toggled label", async () => {
    const user = userEvent.setup();
    render(<CompareToggleButton offerId="offer-1" />);

    expect(
      screen.getByRole("button", { name: "افزودن به مقایسه" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /مشاهده مقایسه/ }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "افزودن به مقایسه" }));

    expect(
      await screen.findByRole("button", { name: "حذف از مقایسه" }),
    ).toBeInTheDocument();
  });

  it("shows a view-comparison link once another offer is already in the list", () => {
    toggleCompareItem("offer-other");
    render(<CompareToggleButton offerId="offer-1" />);

    expect(
      screen.getByRole("link", { name: "مشاهده مقایسه (2)" }),
    ).toHaveAttribute("href", "/shop/offer/offer-1/compare");
  });

  it("disables adding once the bounded cap is reached by other offers", () => {
    for (let i = 0; i < MAX_COMPARE_ITEMS; i += 1) {
      toggleCompareItem(`offer-${i}`);
    }
    render(<CompareToggleButton offerId="offer-not-in-list" />);

    expect(
      screen.getByRole("button", { name: "افزودن به مقایسه" }),
    ).toBeDisabled();
  });
});
