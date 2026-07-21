import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { initiatePayment } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  clearCheckoutAttempt,
  clearLatestOrderId,
} from "@/lib/checkout-attempt";
import { paymentRedirectFixture } from "@/test/fixtures/gate-fixtures";
import { PaymentRedirect } from "./payment-redirect";

vi.mock("@/lib/api/client", () => ({
  initiatePayment: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PaymentRedirect", () => {
  const assign = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    clearCheckoutAttempt();
    clearLatestOrderId();
    assign.mockReset();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, assign },
      writable: true,
    });
  });

  it("starts a real payment for the order and redirects to the returned Zarinpal authority URL", async () => {
    vi.mocked(initiatePayment).mockResolvedValue(paymentRedirectFixture);

    renderWithQuery(<PaymentRedirect orderId="order-1" />);

    expect(
      screen.getByText("در حال انتقال به درگاه پرداخت"),
    ).toBeInTheDocument();
    await waitFor(() => expect(initiatePayment).toHaveBeenCalledTimes(1));
    expect(initiatePayment).toHaveBeenCalledWith(
      "order-1",
      { callback_url: expect.stringContaining("/checkout/payment/return") },
      expect.any(String),
    );
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith(paymentRedirectFixture.redirect_url),
    );
  });

  it("shows a distinct error state with retry when starting payment fails", async () => {
    vi.mocked(initiatePayment).mockRejectedValue(
      new ApiError("خطای سرویس", 500),
    );

    renderWithQuery(<PaymentRedirect orderId="order-1" />);

    expect(
      await screen.findByText("شروع پرداخت انجام نشد"),
    ).toBeInTheDocument();
    expect(assign).not.toHaveBeenCalled();
  });

  it("shows a missing-order error state when no order id is available", () => {
    renderWithQuery(<PaymentRedirect />);

    expect(screen.getByText("شناسه سفارش پیدا نشد")).toBeInTheDocument();
    expect(initiatePayment).not.toHaveBeenCalled();
  });
});
