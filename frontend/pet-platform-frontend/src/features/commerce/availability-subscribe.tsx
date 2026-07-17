"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banner, Button } from "@/components/primitives";
import {
  cancelAvailabilitySubscription,
  listAvailabilitySubscriptions,
  subscribeAvailability,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

function errorText(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 409) return "اطلاع‌رسانی موجودی فعلاً در دسترس نیست.";
    return error.message;
  }
  return "خطا در ارتباط با سرویس.";
}

export function AvailabilitySubscribe({ offerId }: { offerId: string }) {
  const queryClient = useQueryClient();
  const subscriptionsQuery = useQuery({
    queryKey: ["me", "availability-subscriptions"],
    queryFn: listAvailabilitySubscriptions,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ["me", "availability-subscriptions"],
    });

  const subscribeMutation = useMutation({
    mutationFn: () => subscribeAvailability(offerId),
    onSuccess: invalidate,
  });
  const cancelMutation = useMutation({
    mutationFn: () => cancelAvailabilitySubscription(offerId),
    onSuccess: invalidate,
  });

  if (subscriptionsQuery.isLoading) return null;

  const existing = subscriptionsQuery.data?.items.find(
    (item) => item.offer_id === offerId && item.status !== "cancelled",
  );

  const error = subscribeMutation.isError
    ? subscribeMutation.error
    : cancelMutation.isError
      ? cancelMutation.error
      : null;

  if (existing?.status === "active") {
    return (
      <div className="stack">
        <Banner tone="info">
          وقتی این محصول موجود شود، به شما اطلاع داده می‌شود.
        </Banner>
        {error ? <Banner tone="error">{errorText(error)}</Banner> : null}
        <Button
          variant="ghost"
          loading={cancelMutation.isPending}
          onClick={() => cancelMutation.mutate()}
        >
          لغو اطلاع‌رسانی
        </Button>
      </div>
    );
  }

  if (existing?.status === "notified") {
    return (
      <Banner tone="info">
        موجودی این محصول به شما اطلاع داده شده است.
      </Banner>
    );
  }

  return (
    <div className="stack">
      {error ? <Banner tone="error">{errorText(error)}</Banner> : null}
      <Button
        variant="secondary"
        loading={subscribeMutation.isPending}
        onClick={() => subscribeMutation.mutate()}
      >
        اطلاع بده وقتی موجود شد
      </Button>
    </div>
  );
}
