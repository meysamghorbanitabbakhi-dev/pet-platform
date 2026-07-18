import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  acknowledgeOrderDelay,
  getMeContext,
  getOrderDetail,
  getOrderJourney,
} from "@/lib/api/client";
import {
  meContextFixture,
  orderDetailFixture,
  orderJourneyFixture,
} from "@/test/fixtures/gate-fixtures";
import { OrderDetailView } from "./order-detail-view";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/orders/order-1",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  acknowledgeOrderDelay: vi.fn(),
  getMeContext: vi.fn(),
  getOrderDetail: vi.fn(),
  getOrderJourney: vi.fn(),
  replaceOrderPetPlan: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("OrderDetailView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getMeContext).mockResolvedValue({
      ...meContextFixture,
      pets: [],
    });
  });

  it("shows the real authenticity field from the backend, never a hardcoded claim", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      lines: [
        {
          ...orderDetailFixture.lines[0],
          sourced_unit: {
            authenticity: "supplier_verified",
            confirmed_at: "2026-07-18T08:00:00Z",
            exact_expiry_date: "2027-01-01",
            order_line_id: orderDetailFixture.lines[0].id,
            supplier_country: "FR",
          },
        },
      ],
    });
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    expect(
      await screen.findByText(/اصالت: تاییدشده توسط تامین‌کننده/),
    ).toBeInTheDocument();
    expect(screen.getByText(/تاریخ انقضا:/)).toBeInTheDocument();
  });

  it("renders the fulfillment timeline with localized labels, not raw backend event types", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue(orderDetailFixture);
    vi.mocked(getOrderJourney).mockResolvedValue({
      ...orderJourneyFixture,
      timeline: [
        { occurred_at: "2026-07-17T09:05:00Z", type: "payment_confirmed" },
        { occurred_at: "2026-07-18T09:05:00Z", type: "sourcing_started" },
      ],
    });

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    expect(await screen.findByText("پرداخت تایید شد")).toBeInTheDocument();
    expect(screen.getByText("تامین آغاز شد")).toBeInTheDocument();
    expect(screen.queryByText("payment_confirmed")).not.toBeInTheDocument();
  });

  it("shows a delivered banner when the order has been delivered", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      status: "delivered",
    });
    vi.mocked(getOrderJourney).mockResolvedValue({
      ...orderJourneyFixture,
      delivered_at: "2026-07-20T10:00:00Z",
      status: "delivered",
    });

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    expect(
      await screen.findByText(/این سفارش تحویل داده شد/),
    ).toBeInTheDocument();
  });

  it("shows a distinct error banner for a failed order", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      status: "failed",
    });
    vi.mocked(getOrderJourney).mockResolvedValue({
      ...orderJourneyFixture,
      status: "failed",
    });

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    expect(
      await screen.findByText("این سفارش ناموفق ثبت شده است."),
    ).toBeInTheDocument();
  });

  it("shows a revised delivery date and acknowledges the delay through the real backend endpoint", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue(orderDetailFixture);
    vi.mocked(getOrderJourney).mockResolvedValue({
      ...orderJourneyFixture,
      original_delivery_commitment_at: "2026-08-01T15:00:00Z",
      revised_delivery_at: "2026-08-05T15:00:00Z",
    });
    vi.mocked(acknowledgeOrderDelay).mockResolvedValue({
      acknowledged_at: "2026-07-18T09:00:00Z",
      cancellation_implied: false,
      compensation_implied: false,
      delay_event_version: 1,
      id: "ack-1",
      order_id: "order-1",
      waiver_implied: false,
    });
    const user = userEvent.setup();

    renderWithQuery(<OrderDetailView orderId="order-1" />);
    await user.click(await screen.findByRole("button", { name: "متوجه شدم" }));

    await waitFor(() =>
      expect(acknowledgeOrderDelay).toHaveBeenCalledWith(
        orderDetailFixture.id,
        expect.any(String),
      ),
    );
    expect(await screen.findByText("تاخیر تایید شد.")).toBeInTheDocument();
  });
});
