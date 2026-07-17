"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Sheet,
  Skeleton,
} from "@/components/primitives";
import { usePersistedSelectedPet } from "@/features/today/today-dashboard";
import type { JourneyDefinitionResponse, MeContextResponse } from "@/lib/api-types";
import {
  getJourneyDefinition,
  getMeContext,
  startJourney,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

const speciesLabelFa: Record<string, string> = { cat: "گربه", dog: "سگ" };

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

export function JourneyDefinitionDetail({
  definitionId,
}: {
  definitionId: string;
}) {
  const router = useRouter();
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
  });
  const definitionQuery = useQuery({
    queryKey: ["pet-life", "journey-definitions", definitionId],
    queryFn: () => getJourneyDefinition(definitionId),
    enabled: Boolean(definitionId),
  });

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

  if (definitionQuery.isLoading || contextQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (definitionQuery.isError || !definitionQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="این مسیر مراقبتی در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void definitionQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  if (contextQuery.isError || !contextQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="اطلاعات پت در دسترس نیست"
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

  return (
    <JourneyDefinitionBody
      context={contextQuery.data}
      definition={definitionQuery.data}
    />
  );
}

function JourneyDefinitionBody({
  definition,
  context,
}: {
  definition: JourneyDefinitionResponse;
  context: MeContextResponse;
}) {
  const router = useRouter();
  const [showStart, setShowStart] = useState(false);
  const { activePetId, activePet } = usePersistedSelectedPet(context);

  const startMutation = useMutation({
    mutationFn: (petId: string) =>
      startJourney(petId, { definition_id: definition.id }),
    onSuccess: (result) => {
      router.push(`/journeys/active/${result.id}`);
    },
  });

  const eligibleSpecies = definition.content.eligibility.eligible_species;
  const eligibleSpeciesLabel = eligibleSpecies?.length
    ? eligibleSpecies.map((s) => speciesLabelFa[s] ?? s).join("، ")
    : "همه گونه‌های پشتیبانی‌شده";

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">مسیر مراقبتی</div>
          <h1 className="display">{definition.title_fa}</h1>
        </div>

        <Card className="stack">
          {definition.summary_fa ? (
            <p className="caption">{definition.summary_fa}</p>
          ) : null}
          <div className="split">
            <span className="caption">گونه مناسب</span>
            <span>{eligibleSpeciesLabel}</span>
          </div>
          {definition.content.duration_days ? (
            <div className="split">
              <span className="caption">مدت مسیر</span>
              <span>{definition.content.duration_days} روز</span>
            </div>
          ) : null}
          <p className="caption">
            تکمیل این مسیر یک خاطره در دفترچه و یک شیء برای باغ ایرانی پت شما
            به همراه دارد.
          </p>
        </Card>

        <Card className="stack">
          <h2 className="title">گام‌ها</h2>
          <ol className="stack">
            {definition.content.steps.map((step) => (
              <li key={step.key}>
                <div className="title">{step.title_fa}</div>
                <p className="caption">{step.body_fa}</p>
              </li>
            ))}
          </ol>
        </Card>

        {definition.content.exception_behavior.message_fa ? (
          <Banner tone="info">
            {definition.content.exception_behavior.message_fa}
          </Banner>
        ) : null}

        {activePet ? (
          <Button onClick={() => setShowStart(true)}>
            شروع مسیر برای {activePet.name}
          </Button>
        ) : (
          <Banner tone="warning">
            برای شروع این مسیر ابتدا یک پت انتخاب کنید.
          </Banner>
        )}

        {showStart && activePet ? (
          <Sheet
            title="شروع مسیر مراقبتی"
            onClose={() => setShowStart(false)}
          >
            <div className="stack">
              <p className="caption">
                این مسیر برای «{activePet.name}» شروع می‌شود. می‌توانید بعداً
                آن را متوقف یا لغو کنید.
              </p>
              {startMutation.isError ? (
                <Banner tone="error">{errorText(startMutation.error)}</Banner>
              ) : null}
              <div className="cluster">
                <Button
                  loading={startMutation.isPending}
                  onClick={() => startMutation.mutate(activePetId)}
                >
                  تایید شروع
                </Button>
                <Button
                  variant="ghost"
                  disabled={startMutation.isPending}
                  onClick={() => setShowStart(false)}
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
