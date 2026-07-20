import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { readCart } from "@/lib/cart";
import { AddToCartButton } from "./add-to-cart-button";

describe("AddToCartButton", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("adds the server-enforced quantity chosen with the stepper, not always one", async () => {
    const user = userEvent.setup();
    render(<AddToCartButton offerId="offer-1" />);

    await user.click(screen.getByRole("button", { name: "افزایش تعداد" }));
    await user.click(screen.getByRole("button", { name: "افزایش تعداد" }));
    await user.click(screen.getByRole("button", { name: "افزودن به سبد" }));

    expect(readCart().items).toEqual([{ offerId: "offer-1", quantity: 3 }]);
    expect(
      screen.getByRole("button", { name: "به سبد افزوده شد" }),
    ).toBeInTheDocument();
  });

  it("never lets the stepper exceed the server-enforced bound of 100", async () => {
    const user = userEvent.setup();
    render(<AddToCartButton offerId="offer-1" />);

    const increase = screen.getByRole("button", { name: "افزایش تعداد" });
    for (let i = 0; i < 100; i += 1) {
      fireEvent.click(increase);
    }

    expect(increase).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "افزودن به سبد" }));
    expect(readCart().items).toEqual([{ offerId: "offer-1", quantity: 100 }]);
  });

  it("renders a disabled control instead of an active add-to-cart flow for an unavailable offer", () => {
    render(<AddToCartButton disabled offerId="offer-1" />);

    expect(
      screen.getByRole("button", { name: "افزودن به سبد" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("group", { name: "تعداد افزودن به سبد" }),
    ).not.toBeInTheDocument();
  });
});
