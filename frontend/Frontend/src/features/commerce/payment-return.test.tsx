import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { paymentCallback } from "@/lib/api/client";
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
});
