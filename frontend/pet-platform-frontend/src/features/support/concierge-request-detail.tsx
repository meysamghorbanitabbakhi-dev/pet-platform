"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import {
  Button,
  Card,
  ErrorState,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import { getCustomerRequest } from "@/lib/api/client";
import { formatIranDateTime } from "@/lib/format";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";
import {
  promiseLabel,
  requestStatusLabel,
  requestStatusTone,
  requestTypeLabel,
} from "./labels";

export function ConciergeRequestDetail({ requestId }: { requestId: string }) {
  const requestQuery = useQuery({
    queryKey: ["customer-requests", requestId],
    queryFn: () => getCustomerRequest(requestId),
    enabled: Boolean(requestId),
  });

  const sessionExpired = useSessionExpiryRedirect(requestQuery.error);

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

  if (requestQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (requestQuery.isError || !requestQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="این درخواست در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void requestQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  const request = requestQuery.data;
  const unmetPromises = Object.entries(request.promises).filter(
    ([, value]) => value === false,
  );

  return (
    <AppShell>
      <div className="stack">
        <div className="split">
          <div>
            <div className="eyebrow">پشتیبانی</div>
            <h1 className="display">
              {requestTypeLabel(request.request_type)}
            </h1>
          </div>
          <StatusChip tone={requestStatusTone(request.status)}>
            {requestStatusLabel(request.status)}
          </StatusChip>
        </div>

        <Card className="stack">
          <p>{request.message_fa}</p>
          <span className="caption">
            ثبت‌شده در {formatIranDateTime(request.created_at)}
          </span>
        </Card>

        <Card className="stack">
          <div className="eyebrow">اعلامیه</div>
          <p className="caption">{request.acknowledgement_fa}</p>
          {unmetPromises.length ? (
            <ul className="stack">
              {unmetPromises.map(([key]) => (
                <li className="caption" key={key}>
                  این درخواست {promiseLabel(key)} نیست.
                </li>
              ))}
            </ul>
          ) : null}
        </Card>
      </div>
    </AppShell>
  );
}
