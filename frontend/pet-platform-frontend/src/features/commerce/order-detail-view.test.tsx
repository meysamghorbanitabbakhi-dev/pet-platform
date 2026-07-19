import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  acceptShelfLifeException,
  acknowledgeOrderDelay,
  cancelOrder,
  declineShelfLifeException,
  getMeContext,
  getOrderDetail,
  getOrderJourney,
  listShelfLifeExceptions,
  replaceOrderPetPlan,
} from "@/lib/api/client";
import {
  ids,
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
  acceptShelfLifeException: vi.fn(),
  acknowledgeOrderDelay: vi.fn(),
  cancelOrder: vi.fn(),
  declineShelfLifeException: vi.fn(),
  getMeContext: vi.fn(),
  getOrderDetail: vi.fn(),
  getOrderJourney: vi.fn(),
  listShelfLifeExceptions: vi.fn(),
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
    vi.mocked(listShelfLifeExceptions).mockResolvedValue([]);
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

  it("pre-selects each order line's already-saved pet plan instead of always starting blank", async () => {
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      lines: [
        { ...orderDetailFixture.lines[0], planned_pet_ids: [ids.petBishi] },
      ],
    });
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    const bishiCheckbox = await screen.findByRole("checkbox", {
      name: meContextFixture.pets[0].name,
    });
    expect(bishiCheckbox).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: meContextFixture.pets[1].name }),
    ).not.toBeChecked();
  });

  it("assigns different pets to different order lines in the same order, not one pet for the whole order", async () => {
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
    const secondLine = {
      ...orderDetailFixture.lines[0],
      id: "23232323-2323-4232-8232-232323232323",
      title_fa: "پروپلن کت",
      planned_pet_ids: [],
    };
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      lines: [orderDetailFixture.lines[0], secondLine],
    });
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);
    vi.mocked(replaceOrderPetPlan).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<OrderDetailView orderId="order-1" />);
    await screen.findAllByRole("checkbox");

    const groups = screen.getAllByRole("group");
    await user.click(
      within(groups[0]).getByRole("checkbox", {
        name: meContextFixture.pets[0].name,
      }),
    );
    await user.click(
      within(groups[1]).getByRole("checkbox", {
        name: meContextFixture.pets[1].name,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "ثبت برنامه اختیاری" }),
    );

    await waitFor(() =>
      expect(replaceOrderPetPlan).toHaveBeenCalledWith(orderDetailFixture.id, {
        lines: [
          {
            order_line_id: orderDetailFixture.lines[0].id,
            pet_ids: [meContextFixture.pets[0].id],
          },
          {
            order_line_id: secondLine.id,
            pet_ids: [meContextFixture.pets[1].id],
          },
        ],
      }),
    );
  });

  it("lets the customer cancel an eligible order after confirming with a reason", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      cancellation_eligible: true,
    });
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);
    vi.mocked(cancelOrder).mockResolvedValue({
      cancelled_at: "2026-07-19T12:00:00Z",
      order_id: orderDetailFixture.id,
      reason: "قیمت بهتری پیدا کردم",
      refund_amount_irr: orderDetailFixture.merchandise_total_irr,
      refund_auto_processed: false,
      refund_status: "owed",
      status: "cancelled",
    });
    const user = userEvent.setup();

    renderWithQuery(<OrderDetailView orderId="order-1" />);
    await user.click(await screen.findByRole("button", { name: "لغو سفارش" }));

    const confirmButton = screen.getByRole("button", { name: "تایید لغو سفارش" });
    expect(confirmButton).toBeDisabled();

    await user.type(
      screen.getByLabelText("دلیل لغو"),
      "قیمت بهتری پیدا کردم",
    );
    expect(confirmButton).toBeEnabled();
    await user.click(confirmButton);

    await waitFor(() =>
      expect(cancelOrder).toHaveBeenCalledWith(orderDetailFixture.id, {
        reason: "قیمت بهتری پیدا کردم",
      }),
    );
  });

  it("does not offer cancellation once the order is no longer eligible", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      cancellation_eligible: false,
    });
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    await screen.findByText("وضعیت سفارش");
    expect(
      screen.queryByRole("button", { name: "لغو سفارش" }),
    ).not.toBeInTheDocument();
  });

  it("shows the refund-owed disclosure for an already-cancelled order, not a false already-refunded claim", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue({
      ...orderDetailFixture,
      cancellation: {
        cancelled_at: "2026-07-19T12:00:00Z",
        order_id: orderDetailFixture.id,
        reason: "قیمت بهتری پیدا کردم",
        refund_amount_irr: orderDetailFixture.merchandise_total_irr,
        refund_auto_processed: false,
        refund_status: "owed",
        status: "cancelled",
      },
      cancellation_eligible: false,
      status: "cancelled",
    });
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    expect(await screen.findByText(/این سفارش در تاریخ/)).toBeInTheDocument();
    expect(
      screen.getByText(/بازگردانده خواهد شد؛ بازگشت وجه به صورت دستی/),
    ).toBeInTheDocument();
  });

  it("lets the customer accept a proposed shelf-life exception", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue(orderDetailFixture);
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);
    const pending = {
      additional_discount_irr: 200_000,
      id: "sle-1",
      order_line_id: orderDetailFixture.lines[0].id,
      proposed_exact_expiry_date: "2026-09-01",
      reason: "محموله با تاریخ انقضای کوتاه‌تر رسید",
      refund_amount_irr: null,
      refund_auto_processed: false as const,
      refund_status: "not_applicable" as const,
      respond_by: "2026-07-22T12:00:00Z",
      responded_at: null,
      status: "proposed" as const,
    };
    vi.mocked(listShelfLifeExceptions).mockResolvedValue([pending]);
    vi.mocked(acceptShelfLifeException).mockResolvedValue({
      ...pending,
      responded_at: "2026-07-19T12:00:00Z",
      status: "accepted",
    });
    const user = userEvent.setup();

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    expect(
      await screen.findByText(/کوتاه‌تر از تعهد اولیه سفارش است/),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "پذیرش و ادامه سفارش" }),
    );

    await waitFor(() =>
      expect(acceptShelfLifeException).toHaveBeenCalledWith(
        orderDetailFixture.id,
        "sle-1",
      ),
    );
  });

  it("lets the customer decline a proposed shelf-life exception", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue(orderDetailFixture);
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);
    const pending = {
      additional_discount_irr: 0,
      id: "sle-2",
      order_line_id: orderDetailFixture.lines[0].id,
      proposed_exact_expiry_date: "2026-09-01",
      reason: "محموله با تاریخ انقضای کوتاه‌تر رسید",
      refund_amount_irr: null,
      refund_auto_processed: false as const,
      refund_status: "not_applicable" as const,
      respond_by: "2026-07-22T12:00:00Z",
      responded_at: null,
      status: "proposed" as const,
    };
    vi.mocked(listShelfLifeExceptions).mockResolvedValue([pending]);
    vi.mocked(declineShelfLifeException).mockResolvedValue({
      ...pending,
      refund_amount_irr: orderDetailFixture.lines[0].line_total_irr,
      refund_status: "owed",
      responded_at: "2026-07-19T12:00:00Z",
      status: "declined",
    });
    const user = userEvent.setup();

    renderWithQuery(<OrderDetailView orderId="order-1" />);
    await user.click(
      await screen.findByRole("button", { name: "رد و بازگشت وجه" }),
    );

    await waitFor(() =>
      expect(declineShelfLifeException).toHaveBeenCalledWith(
        orderDetailFixture.id,
        "sle-2",
      ),
    );
  });

  it("shows the refund-owed disclosure for a declined exception, not a false already-refunded claim", async () => {
    vi.mocked(getOrderDetail).mockResolvedValue(orderDetailFixture);
    vi.mocked(getOrderJourney).mockResolvedValue(orderJourneyFixture);
    vi.mocked(listShelfLifeExceptions).mockResolvedValue([
      {
        additional_discount_irr: 0,
        id: "sle-3",
        order_line_id: orderDetailFixture.lines[0].id,
        proposed_exact_expiry_date: "2026-09-01",
        reason: "محموله با تاریخ انقضای کوتاه‌تر رسید",
        refund_amount_irr: orderDetailFixture.lines[0].line_total_irr,
        refund_auto_processed: false,
        refund_status: "owed",
        respond_by: "2026-07-22T12:00:00Z",
        responded_at: "2026-07-19T12:00:00Z",
        status: "declined",
      },
    ]);

    renderWithQuery(<OrderDetailView orderId="order-1" />);

    expect(
      await screen.findByText(/این قلم رد شد و تحویل داده نخواهد شد/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/بازگردانده خواهد شد؛ بازگشت وجه به صورت دستی/),
    ).toBeInTheDocument();
  });
});
