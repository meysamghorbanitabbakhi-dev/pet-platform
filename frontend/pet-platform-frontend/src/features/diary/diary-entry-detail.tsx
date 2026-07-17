"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Button, Card, ErrorState, Skeleton } from "@/components/primitives";
import { getDiaryEntry } from "@/lib/api/client";
import { formatIranDateTime } from "@/lib/format";

export function DiaryEntryDetail({
  petId,
  entryId,
}: {
  petId: string;
  entryId: string;
}) {
  const entryQuery = useQuery({
    queryKey: ["pet-life", "diary", petId, entryId],
    queryFn: () => getDiaryEntry(petId, entryId),
    enabled: Boolean(petId && entryId),
  });

  if (entryQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (entryQuery.isError || !entryQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="این خاطره در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void entryQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  const entry = entryQuery.data;

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">دفترچه</div>
          <h1 className="display">{entry.title_fa}</h1>
        </div>

        <Card className="stack">
          <span className="caption">{formatIranDateTime(entry.happened_at)}</span>
          {entry.note_fa ? <p>{entry.note_fa}</p> : null}
        </Card>

        {entry.linked_garden_object ? (
          <Card className="stack">
            <div className="eyebrow">پاداش باغ</div>
            <p className="caption">
              این خاطره یک شیء برای باغ ایرانی پت شما به همراه داشت.
            </p>
            <Link className="button button--selection" href={`/garden/${petId}`}>
              مشاهده باغ
            </Link>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}
