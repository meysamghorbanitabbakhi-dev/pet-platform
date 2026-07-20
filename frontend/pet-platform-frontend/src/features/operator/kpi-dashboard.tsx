"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import { OperatorShell } from "@/components/operator-shell";
import { ApiError } from "@/lib/api/errors";
import { listOperatorKpis } from "@/lib/api/client";
import {
  formatIranDateTime,
  formatPercent,
  formatTomanFromIrr,
} from "@/lib/format";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";

const windowPresets = [
  { key: "7d", label: "۷ روز گذشته", days: 7 },
  { key: "30d", label: "۳۰ روز گذشته", days: 30 },
  { key: "90d", label: "۹۰ روز گذشته", days: 90 },
] as const;

function windowFor(days: number): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end.getTime() - days * 24 * 60 * 60 * 1000);
  return { start: start.toISOString(), end: end.toISOString() };
}

function formatValue(kpi: {
  value: number | null;
  unit: string;
}): string | null {
  if (kpi.value === null) return null;
  if (kpi.unit === "ratio") return formatPercent(Math.round(kpi.value * 100));
  return null;
}

export function KpiDashboard() {
  const [preset, setPreset] =
    useState<(typeof windowPresets)[number]["key"]>("30d");
  const { start, end } = useMemo(() => {
    const active = windowPresets.find((item) => item.key === preset)!;
    return windowFor(active.days);
  }, [preset]);

  const kpisQuery = useQuery({
    queryKey: ["operator-kpis", start, end],
    queryFn: () => listOperatorKpis(start, end),
  });

  const sessionExpired = useSessionExpiryRedirect(kpisQuery.error);
  const forbidden =
    kpisQuery.error instanceof ApiError && kpisQuery.error.status === 403;

  if (sessionExpired) {
    return (
      <OperatorShell>
        <Skeleton />
      </OperatorShell>
    );
  }

  if (forbidden) {
    return (
      <OperatorShell>
        <EmptyState
          title="این صفحه فقط برای اپراتورها در دسترس است"
          body="حساب فعلی شما دسترسی اپراتوری ندارد."
        />
      </OperatorShell>
    );
  }

  if (kpisQuery.isError) {
    return (
      <OperatorShell>
        <ErrorState
          title="شاخص‌های عملکرد در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void kpisQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </OperatorShell>
    );
  }

  return (
    <OperatorShell>
      <div className="stack">
        <div>
          <div className="eyebrow">اپراتور</div>
          <h1 className="display">شاخص‌های عملکرد</h1>
          <p className="caption">
            بازه زمانی بر مبنای ساعت جهانی (UTC) محاسبه می‌شود؛ برای معنای دقیق
            هر شاخص (صورت/مخرج، نحوه شمارش رویدادهای دیرهنگام) به مستندات API
            مراجعه کنید.
          </p>
        </div>

        <div className="cluster" role="radiogroup" aria-label="بازه زمانی">
          {windowPresets.map((item) => (
            <Button
              key={item.key}
              type="button"
              variant={preset === item.key ? "selection" : "secondary"}
              aria-pressed={preset === item.key}
              onClick={() => setPreset(item.key)}
            >
              {item.label}
            </Button>
          ))}
        </div>

        {kpisQuery.isLoading ? (
          <Card className="stack">
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </Card>
        ) : null}

        {kpisQuery.data ? (
          <ul className="stack" aria-label="فهرست شاخص‌ها">
            {kpisQuery.data.map((kpi) => (
              <li key={kpi.key}>
                <Card className="stack">
                  <div className="split">
                    <span className="title">{kpi.name}</span>
                    {kpi.computable ? (
                      <StatusChip tone="info">نسخه {kpi.version}</StatusChip>
                    ) : (
                      <StatusChip tone="muted">غیرقابل محاسبه</StatusChip>
                    )}
                  </div>
                  <p className="caption">{kpi.description}</p>

                  {kpi.computable ? (
                    <div className="split">
                      <span className="ltr-data">
                        {formatValue(kpi) ??
                          (kpi.unit === "irr_total" && kpi.numerator !== null
                            ? formatTomanFromIrr(kpi.numerator)
                            : "—")}
                      </span>
                      <span className="caption ltr-data">
                        {kpi.numerator ?? "—"} / {kpi.denominator ?? "—"}
                      </span>
                    </div>
                  ) : (
                    <p className="caption">{kpi.data_limitation}</p>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        ) : null}

        {kpisQuery.data ? (
          <p className="caption">
            بازه محاسبه‌شده: {formatIranDateTime(start)} تا{" "}
            {formatIranDateTime(end)}
          </p>
        ) : null}
      </div>
    </OperatorShell>
  );
}
