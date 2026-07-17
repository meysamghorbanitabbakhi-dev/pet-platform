"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef } from "react";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { initiatePayment } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  getLatestOrderId,
  getPaymentAttempt,
  setLatestOrderId,
} from "@/lib/checkout-attempt";

function errorText(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 503) {
      return "درگاه پرداخت پیکربندی نشده است. سفارش ساخته شده اما شروع پرداخت زنده نیاز به کلید ارائه‌دهنده دارد.";
    }
    return error.message;
  }
  return "خطا در ارتباط با سرویس پرداخت.";
}

export function PaymentRedirect({ orderId }: { orderId?: string }) {
  const started = useRef(false);
  const activeOrderId = orderId ?? getLatestOrderId();
  const paymentMutation = useMutation({
    mutationFn: async () => {
      if (!activeOrderId) throw new Error("missing-order");
      setLatestOrderId(activeOrderId);
      const attempt = getPaymentAttempt(activeOrderId);
      return initiatePayment(
        activeOrderId,
        { callback_url: `${window.location.origin}/checkout/payment/return` },
        attempt.paymentKey ?? "",
      );
    },
    onSuccess: (response) => {
      window.location.assign(response.redirect_url);
    },
  });

  useEffect(() => {
    if (!activeOrderId || started.current) return;
    started.current = true;
    paymentMutation.mutate();
  }, [activeOrderId, paymentMutation]);

  if (!activeOrderId) {
    return (
      <ErrorState
        title="شناسه سفارش پیدا نشد"
        body="برای شروع پرداخت، سفارش سرویس لازم است."
        action={
          <Link className="button button--primary" href="/checkout/review">
            بازگشت به بازبینی
          </Link>
        }
      />
    );
  }

  if (paymentMutation.isError) {
    return (
      <ErrorState
        title="شروع پرداخت انجام نشد"
        body={errorText(paymentMutation.error)}
        action={
          <div className="cluster">
            <Button
              variant="secondary"
              onClick={() => paymentMutation.mutate()}
              loading={paymentMutation.isPending}
            >
              تلاش دوباره
            </Button>
            <Link
              className="button button--ghost"
              href={`/orders/${activeOrderId}`}
            >
              مشاهده سفارش
            </Link>
          </div>
        }
      />
    );
  }

  return (
    <Card className="stack">
      <div className="eyebrow">درگاه زرین‌پال</div>
      <h2 className="title">در حال انتقال به درگاه پرداخت</h2>
      <Skeleton />
      <Banner tone="info">
        پرداخت کامل است. تامین کالا فقط پس از تایید پرداخت توسط سرویس آغاز
        می‌شود.
      </Banner>
    </Card>
  );
}
