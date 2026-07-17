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
  Skeleton,
} from "@/components/primitives";
import {
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
import { orderStatusLabel, supplierCountryLabel } from "@/lib/commerce-format";
import { clearCheckoutAttempt } from "@/lib/checkout-attempt";
import {
  formatDeliveryCommitment,
  formatIranDateTime,
  formatTomanFromIrr,
} from "@/lib/format";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در دریافت سفارش.";
}

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

  useEffect(() => {
    if (confirmation && orderQuery.data?.payment?.status === "verified") {
      clearCart();
      clearCheckoutAttempt();
    }
  }, [confirmation, orderQuery.data?.payment?.status]);

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
  return (
    <>
      <Card className="stack">
        <div className="split">
          <div>
            <div className="eyebrow">وضعیت سفارش</div>
            <h2 className="title">{orderStatusLabel(order.status)}</h2>
          </div>
          <div className="money">
            {formatTomanFromIrr(order.merchandise_total_irr)}
          </div>
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
      </Card>

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
                  اصالت: تاییدشده توسط تامین‌کننده · کشور تامین‌کننده:{" "}
                  {supplierCountryLabel(line.sourced_unit.supplier_country)}
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
          journey.timeline.map((item) => (
            <div className="split" key={`${item.type}-${item.occurred_at}`}>
              <span>{item.type}</span>
              <span className="caption">
                {formatIranDateTime(item.occurred_at)}
              </span>
            </div>
          ))
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
  const [selectedPetId, setSelectedPetId] = useState<string>("");
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
    retry: false,
  });
  const petPlanMutation = useMutation({
    mutationFn: () =>
      replaceOrderPetPlan(order.id, {
        lines: order.lines.map((line) => ({
          order_line_id: line.id,
          pet_ids: selectedPetId ? [selectedPetId] : [],
        })),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["orders", order.id] });
    },
  });

  const pets = contextQuery.data?.pets ?? [];
  if (!pets.length) return null;

  return (
    <Card className="stack">
      <div>
        <div className="eyebrow">اتصال اختیاری به پت</div>
        <h2 className="title">برنامه پت برای سفارش</h2>
      </div>
      <p className="caption">
        این کار اختیاری است و انبار یا تخمین مصرف غذا ایجاد نمی‌کند.
      </p>
      <select
        className="input"
        value={selectedPetId}
        onChange={(event) => setSelectedPetId(event.target.value)}
        aria-label="انتخاب پت برای برنامه سفارش"
      >
        <option value="">بدون اتصال</option>
        {pets.map((pet) => (
          <option key={pet.id} value={pet.id}>
            {pet.name}
          </option>
        ))}
      </select>
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
