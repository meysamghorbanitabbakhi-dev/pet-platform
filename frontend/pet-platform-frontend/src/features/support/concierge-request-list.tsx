"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import { listCustomerRequests } from "@/lib/api/client";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";
import {
  requestStatusLabel,
  requestStatusTone,
  requestTypeLabel,
} from "./labels";

export function ConciergeRequestList() {
  const requestsQuery = useQuery({
    queryKey: ["customer-requests"],
    queryFn: listCustomerRequests,
  });

  const sessionExpired = useSessionExpiryRedirect(requestsQuery.error);

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
        <div className="split">
          <div>
            <div className="eyebrow">پشتیبانی</div>
            <h1 className="display">درخواست‌های من</h1>
          </div>
          <Link className="button button--primary" href="/support/new">
            درخواست جدید
          </Link>
        </div>

        {requestsQuery.isLoading ? (
          <Card className="stack">
            <Skeleton />
            <Skeleton />
          </Card>
        ) : null}

        {requestsQuery.isError && !sessionExpired ? (
          <ErrorState
            title="فهرست درخواست‌ها در دسترس نیست"
            action={
              <Button
                variant="secondary"
                onClick={() => void requestsQuery.refetch()}
              >
                تلاش دوباره
              </Button>
            }
          />
        ) : null}

        {requestsQuery.data?.items.length === 0 ? (
          <EmptyState
            title="هنوز درخواستی ثبت نشده است"
            body="درخواست‌های پشتیبانی و تامین محصول اینجا نمایش داده می‌شوند."
          />
        ) : null}

        {requestsQuery.data?.items.length ? (
          <ol className="stack" aria-label="فهرست درخواست‌ها">
            {requestsQuery.data.items.map((request) => (
              <li key={request.id}>
                <Link className="card stack" href={`/support/${request.id}`}>
                  <div className="split">
                    <span className="title">
                      {requestTypeLabel(request.request_type)}
                    </span>
                    <StatusChip tone={requestStatusTone(request.status)}>
                      {requestStatusLabel(request.status)}
                    </StatusChip>
                  </div>
                  <span className="caption">{request.message_fa}</span>
                </Link>
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </AppShell>
  );
}
