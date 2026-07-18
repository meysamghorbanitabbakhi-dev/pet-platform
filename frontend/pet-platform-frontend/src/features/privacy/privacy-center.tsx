"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  Skeleton,
  StatusChip,
  Sheet,
} from "@/components/primitives";
import type { PrivacyRequestResponse } from "@/lib/api-types";
import {
  exportMyData,
  listPrivacyRequests,
  requestPrivacyAction,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatIranDateTime } from "@/lib/format";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

const requestTypeLabels: Record<
  PrivacyRequestResponse["request_type"],
  string
> = {
  export: "خروجی اطلاعات",
  disable: "غیرفعال‌سازی حساب",
  anonymize: "ناشناس‌سازی داده‌ها",
};

const statusLabels: Record<PrivacyRequestResponse["status"], string> = {
  requested: "در حال بررسی",
  awaiting_policy: "در انتظار تایید سیاست",
  completed: "انجام‌شده",
  rejected: "رد شده",
};

const statusTones: Record<
  PrivacyRequestResponse["status"],
  "muted" | "info" | "positive"
> = {
  requested: "info",
  awaiting_policy: "info",
  completed: "positive",
  rejected: "muted",
};

function download(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function PrivacyCenter() {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState<"disable" | "anonymize" | null>(
    null,
  );

  const requestsQuery = useQuery({
    queryKey: ["privacy", "requests"],
    queryFn: listPrivacyRequests,
  });

  const exportMutation = useMutation({
    mutationFn: exportMyData,
    onSuccess: (data) => download("pet-platform-data-export.json", data),
  });

  const requestMutation = useMutation({
    mutationFn: (requestType: "disable" | "anonymize") =>
      requestPrivacyAction({ reason: null, request_type: requestType }),
    onSuccess: async () => {
      setConfirming(null);
      // Persist the real status by re-fetching from the backend, not by
      // trusting the one-time creation response alone -- a duplicate active
      // request must show as the same one row, not a second one.
      await queryClient.invalidateQueries({
        queryKey: ["privacy", "requests"],
      });
    },
  });

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">حساب</div>
          <h1 className="display">حریم خصوصی</h1>
        </div>

        <Card className="stack">
          <h2 className="title">خروجی اطلاعات من</h2>
          <p className="caption">
            یک فایل شامل اطلاعات ثبت‌شده حساب شما دانلود می‌شود.
          </p>
          {exportMutation.isError ? (
            <Banner tone="error">{errorText(exportMutation.error)}</Banner>
          ) : null}
          <Button
            variant="secondary"
            loading={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
          >
            دانلود اطلاعات من
          </Button>
        </Card>

        <Card className="stack">
          <h2 className="title">غیرفعال‌سازی و ناشناس‌سازی</h2>
          <p className="caption">
            این اقدام‌ها غیرقابل بازگشت هستند و پس از ثبت درخواست، بررسی و اجرا
            می‌شوند.
          </p>
          <div className="cluster">
            <Button variant="ghost" onClick={() => setConfirming("disable")}>
              درخواست غیرفعال‌سازی حساب
            </Button>
            <Button variant="ghost" onClick={() => setConfirming("anonymize")}>
              درخواست ناشناس‌سازی داده‌ها
            </Button>
          </div>
        </Card>

        <Card className="stack">
          <h2 className="title">درخواست‌های من</h2>
          {requestsQuery.isLoading ? <Skeleton /> : null}
          {requestsQuery.isError ? (
            <Banner tone="error">فهرست درخواست‌ها در دسترس نیست.</Banner>
          ) : null}
          {requestsQuery.data?.items.length === 0 ? (
            <p className="caption">هنوز درخواستی ثبت نشده است.</p>
          ) : null}
          {requestsQuery.data?.items.length ? (
            <ul className="stack" aria-label="فهرست درخواست‌های حریم خصوصی">
              {requestsQuery.data.items.map((item) => (
                <li className="split" key={item.id}>
                  <span>{requestTypeLabels[item.request_type]}</span>
                  <span className="cluster">
                    <span className="caption">
                      {formatIranDateTime(item.created_at)}
                    </span>
                    <StatusChip tone={statusTones[item.status]}>
                      {statusLabels[item.status]}
                    </StatusChip>
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </Card>

        {confirming ? (
          <Sheet
            title={
              confirming === "disable"
                ? "غیرفعال‌سازی حساب"
                : "ناشناس‌سازی داده‌ها"
            }
            onClose={() => setConfirming(null)}
          >
            <div className="stack">
              <Banner tone="warning">
                این اقدام غیرقابل بازگشت است. پس از تایید، امکان لغو درخواست
                وجود ندارد.
              </Banner>
              {requestMutation.isError ? (
                <Banner tone="error">{errorText(requestMutation.error)}</Banner>
              ) : null}
              <div className="cluster">
                <Button
                  loading={requestMutation.isPending}
                  onClick={() => requestMutation.mutate(confirming)}
                >
                  تایید و ثبت درخواست
                </Button>
                <Button
                  variant="ghost"
                  disabled={requestMutation.isPending}
                  onClick={() => setConfirming(null)}
                >
                  انصراف
                </Button>
              </div>
            </div>
          </Sheet>
        ) : null}
      </div>
    </AppShell>
  );
}
