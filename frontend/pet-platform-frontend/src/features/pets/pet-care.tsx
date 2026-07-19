"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import {
  getPetCareGuidance,
  getPetKnowledge,
  setGuidancePreference,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

function KnowledgeSection({ petId }: { petId: string }) {
  const knowledgeQuery = useQuery({
    queryKey: ["knowledge", "pets", petId],
    queryFn: () => getPetKnowledge(petId),
    enabled: Boolean(petId),
  });

  const sessionExpired = useSessionExpiryRedirect(knowledgeQuery.error);

  if (sessionExpired) {
    return <Skeleton />;
  }

  if (knowledgeQuery.isLoading) {
    return (
      <Card className="stack">
        <Skeleton />
      </Card>
    );
  }

  if (knowledgeQuery.isError || !knowledgeQuery.data) {
    return (
      <ErrorState
        title="اطلاعات نژاد در دسترس نیست"
        action={
          <Button
            variant="secondary"
            onClick={() => void knowledgeQuery.refetch()}
          >
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  const knowledge = knowledgeQuery.data;

  if (knowledge.status === "breed_not_recorded") {
    return (
      <Card className="stack">
        <h2 className="title">نژاد</h2>
        <EmptyState
          title="نژاد این پت ثبت نشده است"
          body="با انتخاب نژاد، اطلاعات تاییدشده مرتبط نمایش داده می‌شود."
          action={
            <Link
              className="button button--primary"
              href={`/breeds?petId=${petId}`}
            >
              انتخاب نژاد
            </Link>
          }
        />
        <p className="caption">{knowledge.disclaimer_fa}</p>
      </Card>
    );
  }

  return (
    <Card className="stack">
      <div className="split">
        <h2 className="title">نژاد: {knowledge.breed.name_fa}</h2>
        <Link className="button button--ghost" href={`/breeds?petId=${petId}`}>
          تغییر نژاد
        </Link>
      </div>
      {knowledge.claims.length === 0 ? (
        <p className="caption">اطلاعات تاییدشده‌ای برای این نژاد یافت نشد.</p>
      ) : (
        <ul className="stack" aria-label="نکات تاییدشده نژاد">
          {knowledge.claims.map((claim) => (
            <li className="stack" key={claim.id}>
              <p>{claim.text_fa}</p>
              {claim.sources.length ? (
                <p className="caption">
                  منبع: {claim.sources.map((source) => source.title).join("، ")}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <p className="caption">{knowledge.disclaimer_fa}</p>
    </Card>
  );
}

const domainLabels: Record<string, string> = {
  exercise: "ورزش",
  grooming: "نظافت",
  home: "محیط خانه",
  safety: "ایمنی",
  training: "آموزش",
};

function GuidanceRow({
  petId,
  item,
}: {
  petId: string;
  item: {
    id: string;
    domain: string;
    text_fa: string;
    emergency_classification: string;
  };
}) {
  const queryClient = useQueryClient();
  const [dismissed, setDismissed] = useState(false);

  const preferenceMutation = useMutation({
    mutationFn: (action: "dismiss" | "snooze" | "restore") =>
      setGuidancePreference(
        petId,
        item.id,
        action === "snooze"
          ? {
              action,
              snoozed_until: new Date(
                Date.now() + 7 * 24 * 60 * 60 * 1000,
              ).toISOString(),
            }
          : { action, snoozed_until: null },
      ),
    onSuccess: async (_, action) => {
      setDismissed(action === "dismiss" || action === "snooze");
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "care-guidance", petId],
      });
    },
  });

  if (dismissed) {
    return (
      <li className="split">
        <span className="caption">این راهنما پنهان شد.</span>
        <Button
          variant="ghost"
          onClick={() => preferenceMutation.mutate("restore")}
        >
          بازگرداندن
        </Button>
      </li>
    );
  }

  return (
    <li className="stack">
      <div className="split">
        <span className="eyebrow">
          {domainLabels[item.domain] ?? item.domain}
        </span>
        {item.emergency_classification !== "not_emergency" ? (
          <StatusChip tone="warning">نیازمند توجه</StatusChip>
        ) : null}
      </div>
      <p>{item.text_fa}</p>
      {preferenceMutation.isError ? (
        <Banner tone="error">{errorText(preferenceMutation.error)}</Banner>
      ) : null}
      <div className="cluster">
        <Button
          variant="ghost"
          loading={preferenceMutation.isPending}
          onClick={() => preferenceMutation.mutate("snooze")}
        >
          یادآوری بعداً
        </Button>
        <Button
          variant="ghost"
          loading={preferenceMutation.isPending}
          onClick={() => preferenceMutation.mutate("dismiss")}
        >
          نیازی ندارم
        </Button>
      </div>
    </li>
  );
}

function CareGuidanceSection({ petId }: { petId: string }) {
  const guidanceQuery = useQuery({
    queryKey: ["pet-life", "care-guidance", petId],
    queryFn: () => getPetCareGuidance(petId),
    enabled: Boolean(petId),
  });

  const sessionExpired = useSessionExpiryRedirect(guidanceQuery.error);

  if (sessionExpired) {
    return <Skeleton />;
  }

  if (guidanceQuery.isLoading) {
    return (
      <Card className="stack">
        <Skeleton />
      </Card>
    );
  }

  if (guidanceQuery.isError || !guidanceQuery.data) {
    return (
      <ErrorState
        title="راهنمای مراقبتی در دسترس نیست"
        action={
          <Button
            variant="secondary"
            onClick={() => void guidanceQuery.refetch()}
          >
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  const guidance = guidanceQuery.data;

  return (
    <Card className="stack">
      <h2 className="title">راهنمای مراقبتی</h2>
      {guidance.state === "breed_specific_guidance_unavailable" ? (
        <EmptyState
          title="راهنمای اختصاصی نژاد در دسترس نیست"
          body="با انتخاب نژاد پت، راهنماهای تاییدشده نمایش داده می‌شوند."
        />
      ) : null}
      {guidance.state === "no_eligible_guidance" ? (
        <p className="caption">
          در حال حاضر راهنمای واجد شرایطی برای این پت نیست.
        </p>
      ) : null}
      {guidance.state === "available" ? (
        <ul className="stack" aria-label="فهرست راهنماهای مراقبتی">
          {guidance.items.map((item) => (
            <GuidanceRow item={item} key={item.id} petId={petId} />
          ))}
        </ul>
      ) : null}
      <p className="caption">{guidance.disclaimer_fa}</p>
    </Card>
  );
}

export function PetCare({ petId }: { petId: string }) {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پت</div>
          <h1 className="display">نژاد و راهنمای مراقبتی</h1>
        </div>
        <KnowledgeSection petId={petId} />
        <CareGuidanceSection petId={petId} />
      </div>
    </AppShell>
  );
}
