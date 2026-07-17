"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { paymentCallback } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { paymentCallbackLabel } from "@/lib/commerce-format";
import { setLatestOrderId } from "@/lib/checkout-attempt";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در بررسی نتیجه پرداخت.";
}

export function PaymentReturn({
  authority,
  status,
}: {
  authority?: string;
  status?: string;
}) {
  const router = useRouter();
  const started = useRef(false);
  const callbackMutation = useMutation({
    mutationFn: async () => {
      if (!authority) throw new Error("missing-authority");
      return paymentCallback(authority, status ?? null);
    },
    onSuccess: (response) => {
      if (response.state === "verified" && response.order_id) {
        setLatestOrderId(response.order_id);
        router.replace(`/checkout/confirmation?orderId=${response.order_id}`);
      }
    },
  });

  useEffect(() => {
    if (!authority || started.current) return;
    started.current = true;
    callbackMutation.mutate();
  }, [authority, callbackMutation]);

  if (!authority) {
    return (
      <ErrorState
        title="شناسه پرداخت دریافت نشد"
        body="نتیجه پرداخت بدون شناسه درگاه قابل بررسی نیست."
        action={
          <Link className="button button--primary" href="/cart">
            بازگشت به سبد
          </Link>
        }
      />
    );
  }

  if (callbackMutation.isError) {
    return (
      <ErrorState
        title="نتیجه پرداخت بررسی نشد"
        body={errorText(callbackMutation.error)}
        action={
          <Button
            variant="secondary"
            onClick={() => callbackMutation.mutate()}
            loading={callbackMutation.isPending}
          >
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  if (callbackMutation.data?.state === "cancelled_or_failed") {
    return (
      <Card className="stack">
        <div className="eyebrow">نتیجه پرداخت</div>
        <h2 className="title">
          {paymentCallbackLabel(callbackMutation.data.state)}
        </h2>
        <Banner tone="warning">
          وضعیت پرداخت از پاسخ سرویس خوانده شد. پارامترهای مرورگر مبنای تایید
          سفارش نیستند.
        </Banner>
        <Link className="button button--secondary" href="/checkout/review">
          بازگشت به بازبینی
        </Link>
      </Card>
    );
  }

  return (
    <Card className="stack">
      <div className="eyebrow">نتیجه پرداخت</div>
      <h2 className="title">در حال بررسی پاسخ سرویس</h2>
      <Skeleton />
      <Banner tone="info">
        پرداخت فقط پس از پاسخ تاییدشده سرویس به عنوان پرداخت‌شده نمایش داده
        می‌شود.
      </Banner>
    </Card>
  );
}
