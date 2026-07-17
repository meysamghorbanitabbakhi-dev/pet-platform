"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { ErrorState } from "@/components/primitives";
import {
  getJourneyOffers,
  getMeContext,
  getPolicies,
  getToday,
} from "@/lib/api/client";
import { TodayDashboard, useFixtureSelectedPet } from "./today-dashboard";

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
          title="خطا در دریافت امروز"
          body="اتصال یا نشست را بررسی کنید و دوباره تلاش کنید."
        />
      </AppShell>
    );
  }

  if (!policyQuery.data || !contextQuery.data) {
    return (
      <AppShell>
        <div className="stack">
          <div className="display">امروز</div>
          <div className="card skeleton" />
          <div className="card skeleton" />
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
  const { activePetId, setActivePetId } = useFixtureSelectedPet(context);
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
      />
    </AppShell>
  );
}
