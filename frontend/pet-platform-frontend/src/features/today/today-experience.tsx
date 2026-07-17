"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Button, ErrorState, Skeleton } from "@/components/primitives";
import {
  getJourneyOffers,
  getMeContext,
  getPolicies,
  getToday,
} from "@/lib/api/client";
import { TodayDashboard, usePersistedSelectedPet } from "./today-dashboard";

export function TodayExperience() {
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
  });

  if (policyQuery.isError || contextQuery.isError) {
    return (
      <AppShell>
        <ErrorState
          title="خطا در دریافت Today"
          body="اتصال یا نشست را بررسی کنید و دوباره تلاش کنید."
          action={
            <div className="cluster">
              <Button
                variant="secondary"
                onClick={() => {
                  void policyQuery.refetch();
                  void contextQuery.refetch();
                }}
              >
                تلاش دوباره
              </Button>
              <Link className="button button--ghost" href="/auth/mobile">
                ورود دوباره
              </Link>
            </div>
          }
        />
      </AppShell>
    );
  }

  if (!policyQuery.data || !contextQuery.data) {
    return (
      <AppShell>
        <div className="stack">
          <div className="display">Today</div>
          <Skeleton />
          <Skeleton />
        </div>
      </AppShell>
    );
  }

  return <TodayLoaded policy={policyQuery.data} context={contextQuery.data} />;
}

function TodayLoaded({
  policy,
  context,
}: {
  policy: Awaited<ReturnType<typeof getPolicies>>;
  context: Awaited<ReturnType<typeof getMeContext>>;
}) {
  const { activePetId, setActivePetId } = usePersistedSelectedPet(context);
  const todayQuery = useQuery({
    queryKey: ["pet-life", "today", activePetId],
    queryFn: () => getToday(activePetId),
    enabled: Boolean(activePetId),
  });
  const journeyQuery = useQuery({
    queryKey: ["pet-life", "journey-offers", activePetId],
    queryFn: () => getJourneyOffers(activePetId),
    enabled: Boolean(activePetId && policy.care_journey_delivery_enabled),
  });

  return (
    <AppShell>
      <TodayDashboard
        context={context}
        policy={policy}
        today={todayQuery.data ?? null}
        journeyOffers={journeyQuery.data ?? []}
        activePetId={activePetId}
        onPetSelect={setActivePetId}
        loading={todayQuery.isLoading}
        todayError={todayQuery.isError}
        onTodayRetry={() => void todayQuery.refetch()}
        journeyError={journeyQuery.isError}
        onJourneyRetry={() => void journeyQuery.refetch()}
      />
    </AppShell>
  );
}
