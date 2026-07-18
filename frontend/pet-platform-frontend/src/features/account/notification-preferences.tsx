"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import {
  getPolicies,
  getSmsPreference,
  updateSmsPreference,
} from "@/lib/api/client";
import type { SmsPreferenceResponse } from "@/lib/api-types";
import { ApiError } from "@/lib/api/errors";
import { enabled } from "@/lib/policy";

// The only SMS-preference-gated notification event actually wired up in the
// backend today (see app/modules/notifications/service.py). There is no
// endpoint to list "all notification types" -- preferences are per event_key,
// and this is the one real one, itself hidden while late-credit is not
// customer-visible.
const LATE_CREDIT_EVENT_KEY = "wallet.late_delivery_credit_granted";

function toTimeInputValue(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 5);
}

function toApiTimeValue(value: string): string | null {
  if (!value) return null;
  return `${value}:00`;
}

function errorText(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "خطا در ارتباط با سرویس. دوباره تلاش کنید.";
}

export function NotificationPreferences() {
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });
  const preferenceQuery = useQuery({
    queryKey: ["notification-preferences", LATE_CREDIT_EVENT_KEY, "sms"],
    queryFn: () => getSmsPreference(LATE_CREDIT_EVENT_KEY),
    enabled: Boolean(
      policyQuery.data &&
      enabled(policyQuery.data, "late_credit_customer_visible"),
    ),
  });

  if (policyQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (
    !policyQuery.data ||
    !enabled(policyQuery.data, "late_credit_customer_visible")
  ) {
    return (
      <AppShell>
        <EmptyState
          title="این قابلیت در دسترس نیست"
          body="اعلان پیامکی جبران تأخیر تحویل فعلاً برای حساب شما فعال نشده است."
        />
      </AppShell>
    );
  }

  if (preferenceQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (preferenceQuery.isError || !preferenceQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="تنظیمات اعلان دریافت نشد"
          body="اتصال را بررسی کنید و دوباره تلاش کنید."
          action={
            <Button
              variant="secondary"
              onClick={() => void preferenceQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">اعلان‌ها</div>
          <h1 className="display">تنظیمات پیامک</h1>
        </div>
        <PreferenceForm preference={preferenceQuery.data} />
      </div>
    </AppShell>
  );
}

function PreferenceForm({ preference }: { preference: SmsPreferenceResponse }) {
  const queryClient = useQueryClient();
  const [smsEnabled, setSmsEnabled] = useState(preference.sms_enabled);
  const [quietStart, setQuietStart] = useState(
    toTimeInputValue(preference.quiet_hours_start),
  );
  const [quietEnd, setQuietEnd] = useState(
    toTimeInputValue(preference.quiet_hours_end),
  );
  const [validationError, setValidationError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateSmsPreference(LATE_CREDIT_EVENT_KEY, {
        enabled: smsEnabled,
        quiet_start_local: toApiTimeValue(quietStart),
        quiet_end_local: toApiTimeValue(quietEnd),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["notification-preferences", LATE_CREDIT_EVENT_KEY, "sms"],
      }),
  });

  return (
    <Card className="stack">
      <form
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          setValidationError(null);
          if (Boolean(quietStart) !== Boolean(quietEnd)) {
            setValidationError(
              "برای بازه سکوت، هم زمان شروع و هم زمان پایان لازم است.",
            );
            return;
          }
          saveMutation.mutate();
        }}
      >
        {validationError ? (
          <Banner tone="error">{validationError}</Banner>
        ) : null}
        {saveMutation.isError ? (
          <Banner tone="error">{errorText(saveMutation.error)}</Banner>
        ) : null}
        {saveMutation.isSuccess ? (
          <Banner tone="info">تنظیمات ذخیره شد.</Banner>
        ) : null}

        <div className="field">
          <label htmlFor="sms-enabled-toggle">
            <input
              id="sms-enabled-toggle"
              type="checkbox"
              checked={smsEnabled}
              onChange={(event) => setSmsEnabled(event.target.checked)}
            />{" "}
            اعلان پیامکی جبران تأخیر تحویل فعال باشد
          </label>
        </div>

        <div className="field">
          <label htmlFor="quiet-start">شروع بازه سکوت (اختیاری)</label>
          <input
            id="quiet-start"
            className="input"
            type="time"
            value={quietStart}
            onChange={(event) => setQuietStart(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="quiet-end">پایان بازه سکوت (اختیاری)</label>
          <input
            id="quiet-end"
            className="input"
            type="time"
            value={quietEnd}
            onChange={(event) => setQuietEnd(event.target.value)}
          />
        </div>
        <p className="caption">
          بازه سکوت می‌تواند از شب تا صبح باشد (مثلاً ۲۲:۳۰ تا ۰۷:۰۰).
        </p>

        <Button
          type="submit"
          variant="primary"
          loading={saveMutation.isPending}
        >
          ذخیره
        </Button>
      </form>
    </Card>
  );
}
