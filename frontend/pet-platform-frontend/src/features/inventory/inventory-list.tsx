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
import type { InventoryListItem } from "@/lib/api-types";
import { getMeContext, listHouseholdInventory } from "@/lib/api/client";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";

const stateLabelFa: Record<string, string> = {
  delivered_unopened: "تحویل‌شده، باز نشده",
  exhausted: "تمام‌شده",
  incoming: "در مسیر تحویل",
  opened: "باز شده",
  unavailable: "در دسترس نیست",
};

const stateTone: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  delivered_unopened: "warning",
  exhausted: "muted",
  incoming: "info",
  opened: "positive",
  unavailable: "error",
};

function stateLabel(state: string) {
  return stateLabelFa[state] ?? state;
}

function InventoryRow({ item }: { item: InventoryListItem }) {
  return (
    <Link href={`/inventory/${item.id}`} className="card stack">
      <div className="split">
        <span className="title">{item.label}</span>
        <StatusChip tone={stateTone[item.state] ?? "muted"}>
          {stateLabel(item.state)}
        </StatusChip>
      </div>
      {item.supplier_country ? (
        <span className="caption">مبدا تامین: {item.supplier_country}</span>
      ) : null}
    </Link>
  );
}

export function InventoryList() {
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
  });

  const householdId =
    contextQuery.data?.default_household_id ??
    contextQuery.data?.households[0]?.id ??
    null;

  const inventoryQuery = useQuery({
    queryKey: ["households", householdId, "inventory"],
    queryFn: () => listHouseholdInventory(householdId as string),
    enabled: Boolean(householdId),
  });

  const sessionExpired = useSessionExpiryRedirect(
    contextQuery.error,
    inventoryQuery.error,
  );

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

  if (contextQuery.isError) {
    return (
      <AppShell>
        <ErrorState
          title="خطا در دریافت انبار"
          body="اتصال را بررسی کنید و دوباره تلاش کنید."
          action={
            <Button
              variant="secondary"
              onClick={() => void contextQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  if (contextQuery.data?.onboarding.needs_household) {
    return (
      <AppShell>
        <EmptyState
          title="هنوز خانواری ثبت نشده است"
          body="پس از تکمیل خانوار، واحدهای انبار آن اینجا نمایش داده می‌شوند."
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">خانوار</div>
          <h1 className="display">انبار خانوار</h1>
        </div>

        {!contextQuery.data || (householdId && inventoryQuery.isLoading) ? (
          <Card className="stack">
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </Card>
        ) : null}

        {inventoryQuery.isError ? (
          <ErrorState
            title="فهرست انبار در دسترس نیست"
            action={
              <Button
                variant="secondary"
                onClick={() => void inventoryQuery.refetch()}
              >
                تلاش دوباره
              </Button>
            }
          />
        ) : null}

        {inventoryQuery.data?.length === 0 ? (
          <EmptyState
            title="هنوز واحد انباری ثبت نشده است"
            body="پس از تحویل سفارش، واحدهای انبار خانوار اینجا نمایش داده می‌شوند."
          />
        ) : null}

        {inventoryQuery.data?.length ? (
          <div className="stack" aria-label="فهرست واحدهای انبار">
            {inventoryQuery.data.map((item) => (
              <InventoryRow item={item} key={item.id} />
            ))}
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
