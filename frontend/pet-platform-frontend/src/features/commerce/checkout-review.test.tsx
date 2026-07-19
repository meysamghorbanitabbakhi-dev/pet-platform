import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createOrder, getOfferDetail, getPolicies } from "@/lib/api/client";
import { addCartItem } from "@/lib/cart";
import { writeCheckoutSelection } from "@/lib/checkout-selection";
import {
  ids,
  offerDetailFixture,
  orderResponseFixture,
  policyFixture,
  unavailableOfferFixture,
} from "@/test/fixtures/gate-fixtures";
import { CheckoutReview } from "./checkout-review";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/checkout/review",
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api/client", () => ({
  createOrder: vi.fn(),
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

describe("CheckoutReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    addCartItem(ids.offerDog);
    writeCheckoutSelection({
      addressId: ids.address,
      householdId: ids.household,
    });
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
  });

  it("creates one backend order with stable idempotency after revalidation", async () => {
    vi.mocked(getOfferDetail).mockResolvedValue(offerDetailFixture);
    let resolveOrder: (value: typeof orderResponseFixture) => void = () => {};
    vi.mocked(createOrder).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveOrder = resolve;
        }),
    );
    const user = userEvent.setup();

    renderWithQuery(<CheckoutReview />);
    const submit = await screen.findByRole("button", {
      name: "ساخت سفارش و پرداخت کامل",
    });
    await user.click(submit);
    await user.click(submit);

    expect(createOrder).toHaveBeenCalledTimes(1);
    expect(createOrder).toHaveBeenCalledWith(
      {
        address_id: ids.address,
        household_id: ids.household,
        items: [{ offer_id: ids.offerDog, quantity: 1 }],
      },
      expect.stringMatching(/^checkout-/),
    );

    resolveOrder(orderResponseFixture);
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith(
        `/checkout/payment/redirect?orderId=${ids.orderPaid}`,
      ),
    );
  });

  it("blocks order creation when backend revalidation marks an offer unavailable", async () => {
    vi.mocked(getOfferDetail).mockResolvedValue(unavailableOfferFixture);
    const user = userEvent.setup();

    renderWithQuery(<CheckoutReview />);
    expect(
      await screen.findByText(/موجودی یک یا چند کالا تغییر کرده است/),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "ساخت سفارش و پرداخت کامل" }),
    );

    expect(createOrder).not.toHaveBeenCalled();
  });
});
