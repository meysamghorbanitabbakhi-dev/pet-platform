"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { getBreedDetail, selectPetBreed } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

export function BreedDetail({
  breedId,
  petId,
}: {
  breedId: string;
  petId?: string;
}) {
  const router = useRouter();
  const detailQuery = useQuery({
    queryKey: ["knowledge", "breeds", breedId],
    queryFn: () => getBreedDetail(breedId),
    enabled: Boolean(breedId),
  });

  const selectMutation = useMutation({
    mutationFn: () => {
      if (!petId) throw new Error("no pet selected");
      return selectPetBreed(petId, {
        breed_reference_id: breedId,
        identification_source: "owner_reported",
        selection_mode: "known",
      });
    },
    onSuccess: () => {
      if (petId) router.push(`/pets/${petId}/care`);
    },
  });

  if (detailQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="این نژاد در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void detailQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  const detail = detailQuery.data;

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">دانش نژاد</div>
          <h1 className="display">{detail.breed.name_fa}</h1>
        </div>

        {petId ? (
          <Card className="stack">
            {selectMutation.isError ? (
              <Banner tone="error">{errorText(selectMutation.error)}</Banner>
            ) : null}
            <Button
              loading={selectMutation.isPending}
              onClick={() => selectMutation.mutate()}
            >
              انتخاب این نژاد برای پت
            </Button>
          </Card>
        ) : null}

        {detail.varieties.length ? (
          <Card className="stack">
            <h2 className="title">زیرگونه‌ها</h2>
            <ul className="stack">
              {detail.varieties.map((variety) => (
                <li key={variety.id}>{variety.name_fa}</li>
              ))}
            </ul>
          </Card>
        ) : null}

        <Card className="stack">
          <h2 className="title">نکات تاییدشده</h2>
          {detail.claims.length === 0 ? (
            <p className="caption">
              نکته تاییدشده‌ای برای این نژاد ثبت نشده است.
            </p>
          ) : (
            <ul className="stack">
              {detail.claims.map((claim) => (
                <li className="stack" key={claim.id}>
                  <p>{claim.text_fa}</p>
                  {claim.sources.length ? (
                    <p className="caption">
                      منبع:{" "}
                      {claim.sources.map((source) => source.title).join("، ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>

        {detail.guidance.length ? (
          <Card className="stack">
            <h2 className="title">راهنمای عمومی نژاد</h2>
            <ul className="stack">
              {detail.guidance.map((item) => (
                <li key={item.id}>{item.text_fa}</li>
              ))}
            </ul>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}
