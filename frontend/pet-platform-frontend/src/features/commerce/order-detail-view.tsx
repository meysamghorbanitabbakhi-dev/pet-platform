"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Money,
  OrderTimeline,
  Sheet,
  Skeleton,
} from "@/components/primitives";
import {
  acknowledgeOrderDelay,
  cancelOrder,
  getMeContext,
  getOrderDetail,
  getOrderJourney,
  replaceOrderPetPlan,
} from "@/lib/api/client";
import type {
  OrderDetailResponse,
  OrderJourneyResponse,
} from "@/lib/api-types";
import { ApiError } from "@/lib/api/errors";
import { clearCart } from "@/lib/cart";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";
import {
  authenticityLabel,
  orderStatusLabel,
  supplierCountryLabel,
} from "@/lib/commerce-format";
import { clearCheckoutAttempt } from "@/lib/checkout-attempt";
import {
  formatDeliveryCommitment,
  formatIranDate,
  formatIranDateTime,
  formatTomanFromIrr,
} from "@/lib/format";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در دریافت سفارش.";
}

const timelineEventLabels: Record<string, string> = {
  cancelled: "لغو شد",
  delayed: "تاخیر ثبت شد",
  delivered: "تحویل داده شد",
  in_transit: "در مسیر تحویل",
  payment_confirmed: "پرداخت تایید شد",
  resolution_recorded: "پیگیری ثبت شد",
  sourcing_failed: "تامین ناموفق بود",
  sourcing_started: "تامین آغاز شد",
};

const timelineEventTone: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  cancelled: "muted",
  delayed: "warning",
  delivered: "positive",
  in_transit: "info",
  payment_confirmed: "positive",
  resolution_recorded: "info",
  sourcing_failed: "error",
  sourcing_started: "info",
};

export function OrderDetailView({
  confirmation = false,
  orderId,
}: {
  confirmation?: boolean;
  orderId?: string | null;
}) {
  const orderQuery = useQuery({
    queryKey: ["orders", orderId],
    queryFn: () => getOrderDetail(orderId ?? ""),
    enabled: Boolean(orderId),
  });
  const journeyQuery = useQuery({
    queryKey: ["orders", orderId, "journey"],
    queryFn: () => getOrderJourney(orderId ?? ""),
    enabled: Boolean(orderId),
  });

  const sessionExpired = useSessionExpiryRedirect(
    orderQuery.error,
    journeyQuery.error,
  );

  useEffect(() => {
    if (confirmation && orderQuery.data?.payment?.status === "verified") {
      clearCart();
      clearCheckoutAttempt();
    }
  }, [confirmation, orderQuery.data?.payment?.status]);

  if (sessionExpired) {
    return <Skeleton />;
  }

  if (!orderId) {
    return (
      <EmptyState
        title="سفارش انتخاب نشده است"
        body="برای مشاهده تایید سفارش، شناسه سفارش سرویس لازم است."
        action={
          <Link className="button button--primary" href="/shop">
            رفتن به فروشگاه
          </Link>
        }
      />
    );
  }

  if (orderQuery.isLoading || journeyQuery.isLoading) {
    return (
      <Card className="stack">
        <Skeleton />
        <Skeleton />
        <Skeleton />
      </Card>
    );
  }

  if (orderQuery.isError || journeyQuery.isError) {
    return (
      <ErrorState
        title="سفارش دریافت نشد"
        body={errorText(orderQuery.error ?? journeyQuery.error)}
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void orderQuery.refetch();
              void journeyQuery.refetch();
            }}
          >
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  if (!orderQuery.data || !journeyQuery.data) return null;

  return (
    <div className="stack" data-testid="order-detail">
      {confirmation ? (
        <Banner tone="info">
          سفارش از سرویس دوباره دریافت شد. پرداخت فقط بر اساس وضعیت سرویس نمایش
          داده می‌شود.
        </Banner>
      ) : null}
      <OrderSummary order={orderQuery.data} journey={journeyQuery.data} />
      <OptionalPetPlan order={orderQuery.data} />
    </div>
  );
}

function OrderSummary({
  journey,
  order,
}: {
  journey: OrderJourneyResponse;
  order: OrderDetailResponse;
}) {
  const queryClient = useQueryClient();
  const delayed = Boolean(
    journey.revised_delivery_at &&
    journey.original_delivery_commitment_at &&
    journey.revised_delivery_at !== journey.original_delivery_commitment_at,
  );
  const ackMutation = useMutation({
    mutationFn: () => acknowledgeOrderDelay(order.id, crypto.randomUUID()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["orders", order.id] });
    },
  });
  const [cancelSheetOpen, setCancelSheetOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const cancelMutation = useMutation({
    mutationFn: () => cancelOrder(order.id, { reason: cancelReason }),
    onSuccess: async () => {
      setCancelSheetOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["orders", order.id] });
    },
  });

  return (
    <>
      {order.status === "delivered" ? (
        <Banner tone="info">
          این سفارش تحویل داده شد
          {journey.delivered_at
            ? ` (${formatIranDateTime(journey.delivered_at)})`
            : ""}
          .
        </Banner>
      ) : null}
      {order.status === "failed" ? (
        <Banner tone="error">این سفارش ناموفق ثبت شده است.</Banner>
      ) : null}
      {order.cancellation ? (
        <Banner tone="info">
          این سفارش در تاریخ {formatIranDateTime(order.cancellation.cancelled_at)}{" "}
          لغو شد. مبلغ {formatTomanFromIrr(order.cancellation.refund_amount_irr)}{" "}
          {order.cancellation.refund_status === "operator_attested"
            ? "بازگردانده شد."
            : "بازگردانده خواهد شد؛ بازگشت وجه به صورت دستی توسط تیم پشتیبانی انجام می‌شود و هنوز پرداخت نشده است."}
        </Banner>
      ) : null}

      <Card className="stack">
        <div className="split">
          <div>
            <div className="eyebrow">وضعیت سفارش</div>
            <h2 className="title">{orderStatusLabel(order.status)}</h2>
          </div>
          <Money irr={order.merchandise_total_irr} />
        </div>
        <div className="grid grid--two">
          <Fact
            label="زمان ایجاد"
            value={formatIranDateTime(order.created_at)}
          />
          <Fact
            label="زمان تایید پرداخت"
            value={formatIranDateTime(order.paid_at)}
          />
          <Fact
            label="تعهد تحویل"
            value={formatDeliveryCommitment(
              order.policies.delivery_commitment_hours,
            )}
          />
          <Fact
            label="موعد تحویل سرویس"
            value={formatIranDateTime(order.delivery_commitment_at)}
          />
        </div>
        <Banner tone="info">
          تامین کالا فقط پس از پرداخت کامل موفق آغاز می‌شود. تعهد تحویل این
          سفارش{" "}
          {formatDeliveryCommitment(order.policies.delivery_commitment_hours)}{" "}
          است.
        </Banner>
        {delayed ? (
          <Banner tone="warning">
            زمان تحویل تغییر کرده است. زمان اولیه:{" "}
            {formatIranDateTime(journey.original_delivery_commitment_at)} · زمان
            به‌روزشده: {formatIranDateTime(journey.revised_delivery_at)}
            {ackMutation.isSuccess ? null : (
              <div className="cluster">
                <Button
                  variant="ghost"
                  loading={ackMutation.isPending}
                  onClick={() => ackMutation.mutate()}
                >
                  متوجه شدم
                </Button>
              </div>
            )}
          </Banner>
        ) : null}
        {ackMutation.isSuccess ? (
          <Banner tone="info">تاخیر تایید شد.</Banner>
        ) : null}
        {order.cancellation_eligible ? (
          <div className="cluster">
            <Button variant="ghost" onClick={() => setCancelSheetOpen(true)}>
              لغو سفارش
            </Button>
          </div>
        ) : null}
      </Card>

      {cancelSheetOpen ? (
        <Sheet title="لغو سفارش" onClose={() => setCancelSheetOpen(false)}>
          <div className="stack">
            <p className="caption">
              این سفارش هنوز به تعهد خرید نهایی از تامین‌کننده نرسیده و قابل
              لغو است. پس از لغو، وجه پرداختی به صورت دستی توسط تیم پشتیبانی
              بازگردانده می‌شود و این کار بلافاصله انجام نمی‌شود. لطفاً دلیل
              لغو را بنویسید.
            </p>
            <div className="field">
              <label htmlFor="cancel-reason">دلیل لغو</label>
              <textarea
                id="cancel-reason"
                className="input"
                value={cancelReason}
                onChange={(event) => setCancelReason(event.target.value)}
              />
            </div>
            {cancelMutation.isError ? (
              <Banner tone="error">{errorText(cancelMutation.error)}</Banner>
            ) : null}
            <div className="cluster">
              <Button
                loading={cancelMutation.isPending}
                disabled={cancelReason.trim().length < 5}
                onClick={() => cancelMutation.mutate()}
              >
                تایید لغو سفارش
              </Button>
              <Button variant="ghost" onClick={() => setCancelSheetOpen(false)}>
                انصراف
              </Button>
            </div>
          </div>
        </Sheet>
      ) : null}

      <Card className="stack">
        <div className="eyebrow">اقلام سفارش</div>
        {order.lines.map((line) => (
          <div className="split" key={line.id}>
            <div>
              <div className="title">{line.title_fa}</div>
              <p className="caption">
                تعداد: {line.quantity} · واحد: {line.unit_label_fa}
              </p>
              {line.sourced_unit ? (
                <p className="caption">
                  اصالت: {authenticityLabel(line.sourced_unit.authenticity)} ·
                  کشور تامین‌کننده:{" "}
                  {supplierCountryLabel(line.sourced_unit.supplier_country)}
                </p>
              ) : null}
              {line.sourced_unit?.exact_expiry_date ? (
                <p className="caption">
                  تاریخ انقضا:{" "}
                  {formatIranDate(line.sourced_unit.exact_expiry_date)}
                </p>
              ) : null}
              {line.sourced_unit?.confirmed_at ? (
                <p className="caption">
                  زمان تایید تامین:{" "}
                  {formatIranDateTime(line.sourced_unit.confirmed_at)}
                </p>
              ) : null}
            </div>
            <div className="title">
              {formatTomanFromIrr(line.line_total_irr)}
            </div>
          </div>
        ))}
      </Card>

      <Card className="stack">
        <div className="eyebrow">آدرس تحویل</div>
        <h2 className="title">{order.delivery_address.recipient_name}</h2>
        <p className="caption">
          {order.delivery_address.province}، {order.delivery_address.city}،{" "}
          {order.delivery_address.address_line}
        </p>
      </Card>

      <Card className="stack">
        <div className="eyebrow">مسیر سفارش</div>
        {journey.timeline.length ? (
          <OrderTimeline
            steps={journey.timeline.map((item, index) => ({
              key: `${item.type}-${item.occurred_at}`,
              label: timelineEventLabels[item.type] ?? item.type,
              timestamp: formatIranDateTime(item.occurred_at),
              tone: timelineEventTone[item.type] ?? "muted",
              current: index === journey.timeline.length - 1,
            }))}
          />
        ) : (
          <p className="caption">هنوز رخداد عملیاتی ثبت نشده است.</p>
        )}
      </Card>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="title">{value}</div>
    </div>
  );
}

function OptionalPetPlan({ order }: { order: OrderDetailResponse }) {
  const queryClient = useQueryClient();
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
    retry: false,
  });
  // Reload-safe: seeded once from the server's own planned_pet_ids per line,
  // not reset to blank on every render. Each order line can be connected to
  // a different set of pets (a household with more than one pet may split a
  // single order across them), so state is keyed per line, not one
  // selection applied to the whole order.
  const [linePetIds, setLinePetIds] = useState<Record<string, string[]>>(() =>
    Object.fromEntries(
      order.lines.map((line) => [line.id, line.planned_pet_ids]),
    ),
  );

  const petPlanMutation = useMutation({
    mutationFn: () =>
      replaceOrderPetPlan(order.id, {
        lines: order.lines.map((line) => ({
          order_line_id: line.id,
          pet_ids: linePetIds[line.id] ?? [],
        })),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["orders", order.id] });
    },
  });

  const pets = contextQuery.data?.pets ?? [];
  if (!pets.length) return null;

  function togglePetForLine(lineId: string, petId: string) {
    setLinePetIds((current) => {
      const existing = current[lineId] ?? [];
      const next = existing.includes(petId)
        ? existing.filter((id) => id !== petId)
        : [...existing, petId];
      return { ...current, [lineId]: next };
    });
  }

  return (
    <Card className="stack">
      <div>
        <div className="eyebrow">اتصال اختیاری به پت</div>
        <h2 className="title">برنامه پت برای سفارش</h2>
      </div>
      <p className="caption">
        این کار اختیاری است و انبار یا تخمین مصرف غذا ایجاد نمی‌کند. هر قلم
        سفارش را می‌توان جدا به یک یا چند پت متصل کرد.
      </p>
      <div className="stack">
        {order.lines.map((line) => (
          <div className="stack" key={line.id}>
            <div className="eyebrow">{line.title_fa}</div>
            <div
              className="cluster"
              role="group"
              aria-label={`انتخاب پت برای ${line.title_fa}`}
            >
              {pets.map((pet) => (
                <label key={pet.id}>
                  <input
                    type="checkbox"
                    checked={(linePetIds[line.id] ?? []).includes(pet.id)}
                    onChange={() => togglePetForLine(line.id, pet.id)}
                  />{" "}
                  {pet.name}
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
      {petPlanMutation.isError ? (
        <Banner tone="error">{errorText(petPlanMutation.error)}</Banner>
      ) : null}
      {petPlanMutation.isSuccess ? (
        <Banner tone="info">
          برنامه اختیاری پت در سرویس ثبت شد. انبار یا تخمین غذا ایجاد نشد.
        </Banner>
      ) : null}
      <Button
        variant="secondary"
        onClick={() => petPlanMutation.mutate()}
        loading={petPlanMutation.isPending}
      >
        ثبت برنامه اختیاری
      </Button>
    </Card>
  );
}
