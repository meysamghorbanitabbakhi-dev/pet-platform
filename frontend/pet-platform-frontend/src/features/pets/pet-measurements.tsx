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
  getWeightTrend,
  listMeasurements,
  recordMeasurement,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatIranDate, formatPersianDecimal } from "@/lib/format";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

const measurementTypeLabels: Record<string, string> = {
  body_length: "طول بدن",
  chest_circumference: "دور سینه",
  height_at_withers: "قد تا شانه",
  resting_respiratory_rate: "تعداد تنفس در حالت استراحت",
  temperature: "دما",
  weight: "وزن",
};

function AddWeightForm({ petId }: { petId: string }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");

  const submitMutation = useMutation({
    mutationFn: () =>
      recordMeasurement(petId, {
        confidence: "medium",
        measured_at: new Date().toISOString(),
        measurement_type: "weight",
        source: "owner_reported",
        unit: "kg",
        value: Number.parseFloat(value),
      }),
    onSuccess: async () => {
      setValue("");
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "measurements", petId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "weight-trend", petId],
      });
    },
  });

  return (
    <Card className="stack">
      <h2 className="title">ثبت وزن جدید</h2>
      <div className="field">
        <label htmlFor="weight-value">وزن (کیلوگرم)</label>
        <input
          id="weight-value"
          className="input"
          inputMode="decimal"
          type="number"
          min={0.01}
          step={0.01}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
      </div>
      {submitMutation.isError ? (
        <Banner tone="error">{errorText(submitMutation.error)}</Banner>
      ) : null}
      <Button
        disabled={!(Number.parseFloat(value) > 0) || submitMutation.isPending}
        loading={submitMutation.isPending}
        onClick={() => submitMutation.mutate()}
      >
        ثبت وزن
      </Button>
    </Card>
  );
}

export function PetMeasurements({ petId }: { petId: string }) {
  const measurementsQuery = useQuery({
    queryKey: ["pet-life", "measurements", petId],
    queryFn: () => listMeasurements(petId),
    enabled: Boolean(petId),
  });
  const trendQuery = useQuery({
    queryKey: ["pet-life", "weight-trend", petId],
    queryFn: () => getWeightTrend(petId),
    enabled: Boolean(petId),
  });

  const sessionExpired = useSessionExpiryRedirect(
    measurementsQuery.error,
    trendQuery.error,
  );

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
          <div className="eyebrow">پت</div>
          <h1 className="display">اندازه‌گیری‌ها</h1>
        </div>

        <AddWeightForm petId={petId} />

        <Card className="stack">
          <h2 className="title">روند وزن</h2>
          {trendQuery.isLoading ? <Skeleton /> : null}
          {trendQuery.isError ? (
            <Banner tone="error">روند وزن در دسترس نیست.</Banner>
          ) : null}
          {trendQuery.data?.state === "no_measurements" ? (
            <p className="caption">هنوز وزنی ثبت نشده است.</p>
          ) : null}
          {trendQuery.data?.state === "available" ? (
            <div className="stack">
              <span className="title">
                {formatPersianDecimal(trendQuery.data.current_weight_kg)}{" "}
                کیلوگرم
              </span>
              <span className="caption">
                این روند فقط بر اساس داده‌های همین پت است و تفسیر بالینی ندارد.
              </span>
              {trendQuery.data.changes["30_days"] ? (
                <span className="caption">
                  تغییر نسبت به ۳۰ روز پیش:{" "}
                  {formatPersianDecimal(
                    trendQuery.data.changes["30_days"].change_percent,
                  )}
                  ٪
                </span>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Card className="stack">
          <h2 className="title">تاریخچه اندازه‌گیری</h2>
          {measurementsQuery.isLoading ? <Skeleton /> : null}
          {measurementsQuery.isError ? (
            <ErrorState
              title="تاریخچه در دسترس نیست"
              action={
                <Button
                  variant="secondary"
                  onClick={() => void measurementsQuery.refetch()}
                >
                  تلاش دوباره
                </Button>
              }
            />
          ) : null}
          {measurementsQuery.data?.length === 0 ? (
            <EmptyState
              title="هنوز اندازه‌گیری ثبت نشده است"
              body="با ثبت وزن، تاریخچه اینجا نمایش داده می‌شود."
            />
          ) : null}
          {measurementsQuery.data?.length ? (
            <ul className="stack" aria-label="فهرست اندازه‌گیری‌ها">
              {measurementsQuery.data.map((item) => (
                <li className="split" key={item.id}>
                  <span>
                    {measurementTypeLabels[item.measurement_type] ??
                      item.measurement_type}
                    : {formatPersianDecimal(item.value)} {item.unit}
                  </span>
                  <span className="caption">
                    {formatIranDate(item.measured_at)}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </Card>
      </div>
    </AppShell>
  );
}
