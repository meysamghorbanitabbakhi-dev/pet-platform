"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Money,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import { listOrders } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { orderStatusLabel } from "@/lib/commerce-format";
import { formatIranDate } from "@/lib/format";

const statusTone: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  awaiting_payment: "warning",
  cancelled: "muted",
  delivered: "positive",
  failed: "error",
  in_transit: "info",
  paid: "info",
  refunded: "muted",
  sourcing: "info",
};

const statusFilters = [
  "all",
  "awaiting_payment",
  "paid",
  "sourcing",
  "in_transit",
  "delivered",
  "failed",
] as const;

export function OrderHistory() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] =
    useState<(typeof statusFilters)[number]>("all");
  const ordersQuery = useQuery({ queryKey: ["orders"], queryFn: listOrders });

  const sessionExpired =
    ordersQuery.error instanceof ApiError && ordersQuery.error.status === 401;

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

  if (ordersQuery.isError) {
    return (
      <AppShell>
        <ErrorState
          title="تاریخچه سفارش‌ها در دسترس نیست"
          action={
            <Button variant="secondary" onClick={() => void ordersQuery.refetch()}>
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  const items =
    ordersQuery.data?.items.filter(
      (order) => statusFilter === "all" || order.status === statusFilter,
    ) ?? [];

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">حساب</div>
          <h1 className="display">سفارش‌های من</h1>
        </div>

        {ordersQuery.isLoading ? (
          <Card className="stack">
            <Skeleton />
            <Skeleton />
          </Card>
        ) : null}

        {ordersQuery.data ? (
          <div className="cluster" role="radiogroup" aria-label="فیلتر وضعیت">
            {statusFilters.map((status) => (
              <Button
                key={status}
                type="button"
                variant={statusFilter === status ? "selection" : "secondary"}
                aria-pressed={statusFilter === status}
                onClick={() => setStatusFilter(status)}
              >
                {status === "all" ? "همه" : orderStatusLabel(status)}
              </Button>
            ))}
          </div>
        ) : null}

        {ordersQuery.data && ordersQuery.data.items.length === 0 ? (
          <EmptyState
            title="هنوز سفارشی ثبت نشده است"
            body="سفارش‌های ثبت‌شده اینجا نمایش داده می‌شوند."
            action={
              <Link className="button button--primary" href="/shop">
                رفتن به فروشگاه
              </Link>
            }
          />
        ) : null}

        {ordersQuery.data && ordersQuery.data.items.length > 0 && items.length === 0 ? (
          <p className="caption">سفارشی با این وضعیت یافت نشد.</p>
        ) : null}

        {items.length ? (
          <ul className="stack" aria-label="فهرست سفارش‌ها">
            {items.map((order) => (
              <li key={order.id}>
                <Link className="card stack" href={`/orders/${order.id}`}>
                  <div className="split">
                    <span className="caption ltr-data">
                      {formatIranDate(order.paid_at)}
                    </span>
                    <StatusChip tone={statusTone[order.status] ?? "muted"}>
                      {orderStatusLabel(order.status)}
                    </StatusChip>
                  </div>
                  <Money irr={order.total_irr} />
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </AppShell>
  );
}
