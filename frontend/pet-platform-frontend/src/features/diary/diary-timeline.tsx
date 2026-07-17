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
import { getMeContext, listDiary } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatIranDateTime } from "@/lib/format";

export function DiaryTimeline() {
  const router = useRouter();
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
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

  if (contextQuery.isError || !contextQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="خطا در دریافت دفترچه"
          action={
            <Button variant="secondary" onClick={() => void contextQuery.refetch()}>
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  if (contextQuery.data.pets.length === 0) {
    return (
      <AppShell>
        <EmptyState
          title="ابتدا پتی ثبت کنید"
          body="دفترچه خاطرات مختص هر پت است."
        />
      </AppShell>
    );
  }

  return <DiaryForPet context={contextQuery.data} />;
}

function DiaryForPet({ context }: { context: MeContextResponse }) {
  const { activePetId, activePet, setActivePetId } =
    usePersistedSelectedPet(context);
  const diaryQuery = useQuery({
    queryKey: ["pet-life", "diary", activePetId],
    queryFn: () => listDiary(activePetId),
    enabled: Boolean(activePetId),
  });

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">دفترچه</div>
          <h1 className="display">خاطرات {activePet?.name}</h1>
        </div>

        <PetSwitcher
          pets={context.pets}
          activePetId={activePetId}
          onSelect={setActivePetId}
        />

        {diaryQuery.isLoading ? (
          <Card className="stack">
            <Skeleton />
            <Skeleton />
          </Card>
        ) : null}

        {diaryQuery.isError ? (
          <ErrorState
            title="فهرست دفترچه در دسترس نیست"
            action={
              <Button
                variant="secondary"
                onClick={() => void diaryQuery.refetch()}
              >
                تلاش دوباره
              </Button>
            }
          />
        ) : null}

        {diaryQuery.data?.length === 0 ? (
          <EmptyState
            title="هنوز خاطره‌ای ثبت نشده است"
            body="خاطرات معتبر از مسیرهای مراقبتی و رویدادهای مهم اینجا نمایش داده می‌شوند."
          />
        ) : null}

        {diaryQuery.data?.length ? (
          <ol className="stack" aria-label="فهرست خاطرات">
            {diaryQuery.data.map((entry) => (
              <li key={entry.id}>
                <Link
                  className="card stack"
                  href={`/diary/${activePetId}/${entry.id}`}
                >
                  <span className="title">{entry.title_fa}</span>
                  <span className="caption">
                    {formatIranDateTime(entry.happened_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </AppShell>
  );
}
