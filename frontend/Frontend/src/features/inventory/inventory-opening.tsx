"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { getInventoryDetail, openInventory } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

export function InventoryOpening({ unitId }: { unitId: string }) {
  const queryClient = useQueryClient();
  const detailQuery = useQuery({
    queryKey: ["pet-life", "inventory", unitId],
    queryFn: () => getInventoryDetail(unitId),
    enabled: Boolean(unitId),
  });
  const openMutation = useMutation({
    mutationFn: () =>
      openInventory(unitId, {
        feeding_context: "unknown",
        remaining: null,
        remaining_grams: null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "inventory", unitId],
      });
    },
  });

  if (detailQuery.isLoading) {
    return (
      <AppShell>
        <div className="stack">
          <h1 className="display">باز کردن بسته</h1>
          <Card className="stack">
            <Skeleton />
            <Skeleton />
            <Skeleton />
          </Card>
        </div>
      </AppShell>
    );
  }

  if (detailQuery.isError) {
    return (
      <AppShell>
        <ErrorState
          title="واحد انبار دریافت نشد"
          body={errorText(detailQuery.error)}
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
  if (!detail) {
    return (
      <AppShell>
        <ErrorState title="واحد انبار در دسترس نیست" />
      </AppShell>
    );
  }

  const alreadyOpened = Boolean(detail.opened_at) || detail.state === "opened";
  const unavailable = detail.state === "unavailable";

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">انبار خانوار</div>
          <h1 className="display">باز کردن بسته</h1>
        </div>
        <Card className="stack">
          <div>
            <div className="eyebrow">شناسه واحد</div>
            <div className="ltr-data">{detail.id}</div>
          </div>
          <h2 className="title">{detail.label}</h2>
          <p className="caption">
            این واحد فیزیکی متعلق به خانوار است. مصرف پت پس از آماده‌سازی جدا
            ثبت می‌شود.
          </p>
          {unavailable ? (
            <Banner tone="error">
              این واحد انبار برای باز کردن در دسترس نیست.
            </Banner>
          ) : alreadyOpened ? (
            <Banner tone="info">
              باز شدن بسته قبلاً ثبت شده است. تخمین فقط از داده سرویس نمایش داده
              می‌شود.
            </Banner>
          ) : (
            <>
              <Banner tone="warning">
                تا قبل از تایید باز شدن بسته، تخمین روز باقی‌مانده شروع نمی‌شود.
              </Banner>
              <Button
                onClick={() => openMutation.mutate()}
                loading={openMutation.isPending}
                disabled={openMutation.isPending}
              >
                تایید باز شدن بسته
              </Button>
            </>
          )}
          {openMutation.isError ? (
            <Banner tone="error">{errorText(openMutation.error)}</Banner>
          ) : null}
          {openMutation.isSuccess ? (
            <Banner tone="info">
              باز شدن بسته ثبت شد. اگر سرویس تخمین معتبر برگرداند، همان داده
              نمایش داده می‌شود.
            </Banner>
          ) : null}
        </Card>
      </div>
    </AppShell>
  );
}

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}
