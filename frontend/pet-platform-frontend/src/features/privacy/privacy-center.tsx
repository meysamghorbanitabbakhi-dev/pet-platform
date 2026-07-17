"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Banner, Button, Card, Sheet } from "@/components/primitives";
import { exportMyData, requestPrivacyAction } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

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
  const [confirming, setConfirming] = useState<"disable" | "anonymize" | null>(
    null,
  );

  const exportMutation = useMutation({
    mutationFn: exportMyData,
    onSuccess: (data) => download("pet-platform-data-export.json", data),
  });

  const requestMutation = useMutation({
    mutationFn: (requestType: "disable" | "anonymize") =>
      requestPrivacyAction({ reason: null, request_type: requestType }),
    onSuccess: () => setConfirming(null),
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

        {requestMutation.isSuccess ? (
          <Banner tone="info">
            درخواست شما با شناسه {requestMutation.data.id} ثبت شد. وضعیت فعلی:{" "}
            {requestMutation.data.status}
          </Banner>
        ) : null}

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
