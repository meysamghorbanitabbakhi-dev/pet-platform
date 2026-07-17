"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PetSwitcher,
  Skeleton,
} from "@/components/primitives";
import { usePersistedSelectedPet } from "@/features/today/today-dashboard";
import type { MeContextResponse } from "@/lib/api-types";
import {
  getJourneyOffers,
  getMeContext,
  getPolicies,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { enabled } from "@/lib/policy";

export function JourneysList() {
  const router = useRouter();
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
  });
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });

  const sessionExpired =
    contextQuery.error instanceof ApiError && contextQuery.error.status === 401;

  useEffect(() => {
    if (sessionExpired) router.replace("/auth/session-expired");
  }, [sessionExpired, router]);

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

  if (contextQuery.isError || policyQuery.isError) {
    return (
      <AppShell>
        <ErrorState
          title="خطا در دریافت مسیرهای مراقبتی"
          body="اتصال را بررسی کنید و دوباره تلاش کنید."
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void contextQuery.refetch();
                void policyQuery.refetch();
              }}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  if (!contextQuery.data || !policyQuery.data) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (!enabled(policyQuery.data, "care_journey_delivery_enabled")) {
    return (
      <AppShell>
        <EmptyState
          title="مسیرهای مراقبتی در دسترس نیست"
          body="این قابلیت فعلاً برای حساب شما فعال نشده است."
        />
      </AppShell>
    );
  }

  if (contextQuery.data.pets.length === 0) {
    return (
      <AppShell>
        <EmptyState
          title="ابتدا پتی ثبت کنید"
          body="مسیرهای مراقبتی مختص هر پت است."
          action={
            <Link className="button button--primary" href="/onboarding/pet">
              افزودن پت
            </Link>
          }
        />
      </AppShell>
    );
  }

  return <JourneysForPet context={contextQuery.data} />;
}

function JourneysForPet({ context }: { context: MeContextResponse }) {
  const { activePetId, setActivePetId } = usePersistedSelectedPet(context);
  const offersQuery = useQuery({
    queryKey: ["pet-life", "journey-offers", activePetId],
    queryFn: () => getJourneyOffers(activePetId),
    enabled: Boolean(activePetId),
  });

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">مراقبت</div>
          <h1 className="display">مسیرهای مراقبتی</h1>
        </div>

        <PetSwitcher
          pets={context.pets}
          activePetId={activePetId}
          onSelect={setActivePetId}
        />

        {offersQuery.isLoading ? (
          <Card className="stack">
            <Skeleton />
            <Skeleton />
          </Card>
        ) : null}

        {offersQuery.isError ? (
          <ErrorState
            title="فهرست مسیرها در دسترس نیست"
            action={
              <Button
                variant="secondary"
                onClick={() => void offersQuery.refetch()}
              >
                تلاش دوباره
              </Button>
            }
          />
        ) : null}

        {offersQuery.data?.length === 0 ? (
          <EmptyState
            title="مسیر مراقبتی فعالی برای این پت وجود ندارد"
            body="مسیرهای تاییدشده و مرتبط با گونه این پت، در صورت وجود، اینجا نمایش داده می‌شوند."
          />
        ) : null}

        {offersQuery.data?.length ? (
          <div className="stack" aria-label="فهرست مسیرهای مراقبتی">
            {offersQuery.data.map((offer) => (
              <Link
                className="card stack"
                href={`/journeys/${offer.definition_id}`}
                key={offer.definition_id}
              >
                <span className="title">{offer.title_fa}</span>
                {offer.summary_fa ? (
                  <span className="caption">{offer.summary_fa}</span>
                ) : null}
                {offer.duration_days ? (
                  <span className="caption">
                    مدت: {offer.duration_days} روز
                  </span>
                ) : null}
              </Link>
            ))}
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
