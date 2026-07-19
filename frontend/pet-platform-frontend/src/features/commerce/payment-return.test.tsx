import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { paymentCallback } from "@/lib/api/client";
import { setLatestOrderId } from "@/lib/checkout-attempt";
import { ids, paymentCallbackFixture } from "@/test/fixtures/gate-fixtures";
import { PaymentReturn } from "./payment-return";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/checkout/payment/return",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  paymentCallback: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PaymentReturn", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("does not confirm payment from browser query parameters alone", async () => {
    vi.mocked(paymentCallback).mockResolvedValue({
      delivery_commitment_at: null,
      order_id: null,
      state: "cancelled_or_failed",
    });

    renderWithQuery(<PaymentReturn authority="unknown" status="OK" />);

    expect(
      await screen.findByText("پرداخت توسط سرویس تایید نشد"),
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(paymentCallback).toHaveBeenCalledWith("unknown", "OK");
  });

  it("routes to confirmation only from verified backend callback response", async () => {
    vi.mocked(paymentCallback).mockResolvedValue(paymentCallbackFixture);

    renderWithQuery(
      <PaymentReturn authority="fixture-authority" status="OK" />,
    );

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith(
        `/checkout/confirmation?orderId=${ids.orderPaid}`,
      ),
    );
  });

  it("shows a calm recovery state, not an alarming failure, when the callback check itself errors", async () => {
    vi.mocked(paymentCallback).mockRejectedValue(new Error("network down"));
    setLatestOrderId(ids.orderPaid);

    renderWithQuery(
      <PaymentReturn authority="fixture-authority" status="OK" />,
    );

    expect(
      await screen.findByText("وضعیت پرداخت هنوز مشخص نشد"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "مشاهده سفارش" })).toHaveAttribute(
      "href",
      `/orders/${ids.orderPaid}`,
    );
    expect(
      screen.getByRole("link", { name: "بازگشت به امروز" }),
    ).toHaveAttribute("href", "/today");
    expect(
      screen.getByRole("link", { name: "تماس با پشتیبانی" }),
    ).toHaveAttribute("href", "/support/new");
    expect(replace).not.toHaveBeenCalled();
  });

  it("does not offer a view-order link when no order id has been recorded for this attempt", async () => {
    vi.mocked(paymentCallback).mockRejectedValue(new Error("network down"));

    renderWithQuery(
      <PaymentReturn authority="fixture-authority" status="OK" />,
    );

    await screen.findByText("وضعیت پرداخت هنوز مشخص نشد");
    expect(
      screen.queryByRole("link", { name: "مشاهده سفارش" }),
    ).not.toBeInTheDocument();
  });
});
