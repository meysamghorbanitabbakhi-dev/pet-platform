"use client";

import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { createOrder, getOfferDetail, getPolicies } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { cartSignature } from "@/lib/cart";
import { getOrderAttempt, markOrderCreated } from "@/lib/checkout-attempt";
import { readCheckoutSelection } from "@/lib/checkout-selection";
import { formatDeliveryCommitment, formatTomanFromIrr } from "@/lib/format";
import { useCartSnapshot } from "./use-cart";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس. دوباره تلاش کنید.";
}

export function CheckoutReview() {
  const cart = useCartSnapshot();
  const router = useRouter();
  const selection = readCheckoutSelection();
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });
  const offerQueries = useQueries({
    queries: cart.items.map((item) => ({
      queryKey: ["catalog", "offer", item.offerId],
      queryFn: () => getOfferDetail(item.offerId),
      staleTime: 0,
    })),
  });
  const createOrderMutation = useMutation({
    mutationFn: async () => {
      if (!selection) throw new Error("missing-selection");
      const signature = cartSignature(
        cart,
        `${selection.householdId}:${selection.addressId}`,
      );
      const attempt = getOrderAttempt(signature);
      if (attempt.orderId) return { id: attempt.orderId };
      const response = await createOrder(
        {
          address_id: selection.addressId,
          household_id: selection.householdId,
          items: cart.items.map((item) => ({
            offer_id: item.offerId,
            quantity: item.quantity,
          })),
        },
        attempt.orderKey,
      );
      markOrderCreated(signature, response.id);
      return response;
    },
    onSuccess: (order) => {
      router.push(`/checkout/payment/redirect?orderId=${order.id}`);
    },
  });

  if (!cart.items.length) {
    return (
      <EmptyState
        title="سبد خرید خالی است"
        body="برای ساخت سفارش، کالاهای سبد باید از سرویس بازخوانی شوند."
        action={
          <Link className="button button--primary" href="/shop">
            رفتن به فروشگاه
          </Link>
        }
      />
    );
  }

  if (!selection) {
    return (
      <ErrorState
        title="آدرس انتخاب نشده است"
        body="برای ادامه پرداخت، آدرس تحویل را انتخاب یا ثبت کنید."
        action={
          <Link className="button button--primary" href="/checkout/address">
            انتخاب آدرس
          </Link>
        }
      />
    );
  }

  if (policyQuery.isLoading || offerQueries.some((query) => query.isLoading)) {
    return (
      <Card className="stack">
        <Skeleton />
        <Skeleton />
        <Skeleton />
      </Card>
    );
  }

  if (policyQuery.isError || offerQueries.some((query) => query.isError)) {
    return (
      <ErrorState
        title="بازبینی سفارش کامل نشد"
        body="قیمت، موجودی و سیاست پرداخت باید از سرویس دریافت شوند."
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void policyQuery.refetch();
              offerQueries.forEach((query) => void query.refetch());
            }}
          >
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  const policy = policyQuery.data;
  const rows = cart.items.map((item, index) => ({
    item,
    offer: offerQueries[index]?.data ?? null,
  }));
  const totalIrr = rows.reduce(
    (sum, row) => sum + (row.offer?.price_irr ?? 0) * row.item.quantity,
    0,
  );
  const unavailable = rows.some(
    (row) => row.offer?.availability !== "available",
  );
  const policyBlocked =
    !policy ||
    !policy.full_payment_only ||
    policy.delivery_commitment_hours !== 366 ||
    policy.reserve_now_enabled;

  return (
    <div className="stack">
      <Banner tone="info">
        سفارش با پرداخت کامل ساخته می‌شود. تامین کالا فقط پس از تایید پرداخت
        کامل توسط سرویس آغاز می‌شود.
      </Banner>
      {policyBlocked ? (
        <Banner tone="error">
          سیاست اجرا با پرداخت کامل، تعهد ۳۶۶ ساعت یا رزرو غیرفعال سازگار نیست.
        </Banner>
      ) : null}
      {unavailable ? (
        <Banner tone="error">
          موجودی یک یا چند کالا تغییر کرده است. سبد را اصلاح کنید.
        </Banner>
      ) : null}

      <Card className="stack">
        <div className="eyebrow">اقلام سفارش</div>
        {rows.map(({ item, offer }) =>
          offer ? (
            <div className="split" key={item.offerId}>
              <div>
                <div className="title">{offer.title_fa}</div>
                <p className="caption">تعداد: {item.quantity}</p>
              </div>
              <div className="title">
                {formatTomanFromIrr(
                  offer.price_irr * item.quantity,
                  policy?.irr_per_customer_display_unit,
                )}
              </div>
            </div>
          ) : null,
        )}
      </Card>

      <Card className="stack">
        <div className="split">
          <div>
            <div className="eyebrow">جمع قابل پرداخت</div>
            <div className="money">
              {formatTomanFromIrr(
                totalIrr,
                policy?.irr_per_customer_display_unit,
              )}
            </div>
          </div>
          <div>
            <div className="eyebrow">تعهد تحویل</div>
            <div className="title">
              {formatDeliveryCommitment(
                policy?.delivery_commitment_hours ?? 366,
              )}
            </div>
          </div>
        </div>
        {createOrderMutation.isError ? (
          <Banner tone="error">{errorText(createOrderMutation.error)}</Banner>
        ) : null}
        <div className="cluster">
          <Button
            onClick={() => createOrderMutation.mutate()}
            loading={createOrderMutation.isPending}
            disabled={
              createOrderMutation.isPending || unavailable || policyBlocked
            }
          >
            ساخت سفارش و پرداخت کامل
          </Button>
          <Link className="button button--secondary" href="/checkout/address">
            تغییر آدرس
          </Link>
        </div>
      </Card>
    </div>
  );
}
