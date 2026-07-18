"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import type { NotificationListItem } from "@/lib/api-types";
import {
  getPolicies,
  listNotifications,
  markNotificationRead,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatIranDateTime } from "@/lib/format";
import { notificationDestinationHref } from "@/lib/notification-destination";
import { enabled } from "@/lib/policy";

const eventLabels: Record<string, string> = {
  "catalog.offer_available": "محصولی که منتظرش بودید موجود شد",
  "wallet.late_delivery_credit_granted":
    "اعتبار کیف پول بابت تاخیر تحویل ثبت شد",
};

function eventLabel(key: string) {
  return eventLabels[key] ?? key;
}

function NotificationRow({ item }: { item: NotificationListItem }) {
  const queryClient = useQueryClient();
  const readMutation = useMutation({
    mutationFn: () => markNotificationRead(item.id),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["pet-life", "notifications"],
      }),
  });
  const read = Boolean(item.read_at);
  const href = notificationDestinationHref(item.destination);

  return (
    <li>
      <Card className="stack">
        <div className="split">
          {href ? (
            <Link className="title" href={href}>
              {eventLabel(item.event_key)}
            </Link>
          ) : (
            <span className="title">{eventLabel(item.event_key)}</span>
          )}
          <StatusChip tone={read ? "muted" : "info"}>
            {read ? "خوانده‌شده" : "خوانده‌نشده"}
          </StatusChip>
        </div>
        <span className="caption">{formatIranDateTime(item.created_at)}</span>
        {!read ? (
          <Button
            variant="ghost"
            loading={readMutation.isPending}
            onClick={() => readMutation.mutate()}
          >
            علامت‌گذاری به‌عنوان خوانده‌شده
          </Button>
        ) : null}
      </Card>
    </li>
  );
}

export function NotificationInbox() {
  const router = useRouter();
  const notificationsQuery = useQuery({
    queryKey: ["pet-life", "notifications"],
    queryFn: listNotifications,
  });
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });

  const sessionExpired =
    notificationsQuery.error instanceof ApiError &&
    notificationsQuery.error.status === 401;

  useEffect(() => {
    if (sessionExpired) router.replace("/auth/session-expired");
  }, [sessionExpired, router]);

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">حساب</div>
          <h1 className="display">اعلان‌ها</h1>
        </div>

        {policyQuery.data &&
        !enabled(policyQuery.data, "push_notifications_enabled") ? (
          <Banner tone="info">
            اعلان‌های فوری (push) در حال حاضر فعال نیست. اعلان‌ها فقط در همین
            صندوق ورودی نمایش داده می‌شوند.
          </Banner>
        ) : null}

        <Link
          className="button button--ghost"
          href="/account/notifications/preferences"
        >
          تنظیمات پیامک
        </Link>

        {notificationsQuery.isLoading ? (
          <Card className="stack">
            <Skeleton />
            <Skeleton />
          </Card>
        ) : null}

        {notificationsQuery.isError && !sessionExpired ? (
          <ErrorState
            title="صندوق اعلان‌ها در دسترس نیست"
            action={
              <Button
                variant="secondary"
                onClick={() => void notificationsQuery.refetch()}
              >
                تلاش دوباره
              </Button>
            }
          />
        ) : null}

        {notificationsQuery.data?.items.length === 0 ? (
          <EmptyState
            title="صندوق اعلان‌ها خالی است"
            body="اعلان‌های مربوط به سفارش‌ها و موجودی محصولات اینجا نمایش داده می‌شوند."
          />
        ) : null}

        {notificationsQuery.data?.items.length ? (
          <ul className="stack" aria-label="فهرست اعلان‌ها">
            {notificationsQuery.data.items.map((item) => (
              <NotificationRow item={item} key={item.id} />
            ))}
          </ul>
        ) : null}
      </div>
    </AppShell>
  );
}
