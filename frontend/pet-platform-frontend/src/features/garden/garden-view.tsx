"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  GardenObject,
  Sheet,
  Skeleton,
} from "@/components/primitives";
import type { GardenObjectResponse } from "@/lib/api-types";
import {
  getGarden,
  placeGardenObject,
  returnGardenObject,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

const spots = [
  { label: "بالا راست", x: 750, y: 250 },
  { label: "بالا وسط", x: 500, y: 250 },
  { label: "بالا چپ", x: 250, y: 250 },
  { label: "وسط راست", x: 750, y: 500 },
  { label: "وسط وسط", x: 500, y: 500 },
  { label: "وسط چپ", x: 250, y: 500 },
  { label: "پایین راست", x: 750, y: 750 },
  { label: "پایین وسط", x: 500, y: 750 },
  { label: "پایین چپ", x: 250, y: 750 },
] as const;

function PlacementSheet({
  object,
  quadrant,
  onClose,
}: {
  object: GardenObjectResponse;
  quadrant: number;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const placeMutation = useMutation({
    mutationFn: (spot: { x: number; y: number }) =>
      placeGardenObject(object.id, {
        position_x: spot.x,
        position_y: spot.y,
        quadrant,
      }),
    onSuccess: async () => {
      onClose();
      await queryClient.invalidateQueries({ queryKey: ["pet-life", "garden"] });
    },
  });

  return (
    <Sheet title="قرار دادن در باغ" onClose={onClose}>
      <div className="stack">
        <p className="caption">یک جایگاه برای این شیء انتخاب کنید.</p>
        {placeMutation.isError ? (
          <Banner tone="error">{errorText(placeMutation.error)}</Banner>
        ) : null}
        <div className="grid grid--two">
          {spots.map((spot) => (
            <Button
              key={spot.label}
              variant="secondary"
              disabled={placeMutation.isPending}
              onClick={() => placeMutation.mutate({ x: spot.x, y: spot.y })}
            >
              {spot.label}
            </Button>
          ))}
        </div>
      </div>
    </Sheet>
  );
}

function PlacedObjectActions({
  object,
  onClose,
  onMove,
  onReturn,
  returning,
  returnError,
}: {
  object: GardenObjectResponse;
  onClose: () => void;
  onMove: () => void;
  onReturn: () => void;
  returning: boolean;
  returnError: string | null;
}) {
  return (
    <Sheet title={object.object_key} onClose={onClose}>
      <div className="stack">
        {returnError ? <Banner tone="error">{returnError}</Banner> : null}
        <div className="cluster">
          <Button variant="secondary" onClick={onMove}>
            جابه‌جایی
          </Button>
          <Button variant="ghost" loading={returning} onClick={onReturn}>
            بازگرداندن به انبار
          </Button>
        </div>
      </div>
    </Sheet>
  );
}

export function GardenView({
  petId,
  highlightedRewardId,
}: {
  petId: string;
  highlightedRewardId?: string;
}) {
  const queryClient = useQueryClient();
  const [placing, setPlacing] = useState<GardenObjectResponse | null>(null);
  const [managing, setManaging] = useState<GardenObjectResponse | null>(null);

  const gardenQuery = useQuery({
    queryKey: ["pet-life", "garden", petId],
    queryFn: () => getGarden(petId),
    enabled: Boolean(petId),
  });

  const returnMutation = useMutation({
    mutationFn: (rewardId: string) => returnGardenObject(rewardId),
    onSuccess: async () => {
      setManaging(null);
      await queryClient.invalidateQueries({ queryKey: ["pet-life", "garden"] });
    },
  });

  if (gardenQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (gardenQuery.isError || !gardenQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="باغ در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void gardenQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  const garden = gardenQuery.data;
  const revealed = garden.objects.filter((o) => o.state === "revealed");
  const stored = garden.objects.filter((o) => o.state === "stored");
  const placed = garden.objects.filter((o) => o.state === "placed");
  const unlockedQuadrant = garden.unlocked_quadrants[0] ?? 1;

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">باغ ایرانی</div>
          <h1 className="display">باغ پت</h1>
        </div>

        {garden.objects.length === 0 ? (
          <EmptyState
            title="باغ هنوز خالی است"
            body="پاداش‌های باغ فقط از خاطره‌های معتبر (مثل تکمیل یک مسیر مراقبتی) به دست می‌آیند، نه خرید یا امتیاز."
          />
        ) : null}

        {revealed.length ? (
          <Card className="stack">
            <div className="eyebrow">پاداش تازه</div>
            <div className="cluster">
              {revealed.map((object) => (
                <GardenObject
                  key={object.id}
                  label={
                    object.id === highlightedRewardId
                      ? "پاداش جدید شما"
                      : object.object_key
                  }
                  placed={false}
                  onClick={() => setPlacing(object)}
                />
              ))}
            </div>
            <p className="caption">
              برای قرار دادن این شیء در باغ، روی آن ضربه بزنید.
            </p>
          </Card>
        ) : null}

        <Card className="stack">
          <div className="eyebrow">باغ</div>
          {placed.length === 0 ? (
            <p className="caption">هنوز شیئی در باغ قرار نگرفته است.</p>
          ) : (
            <div className="cluster" aria-label="اشیای قرارگرفته در باغ">
              {placed.map((object) => (
                <GardenObject
                  key={object.id}
                  label={object.object_key}
                  placed
                  onClick={() => setManaging(object)}
                />
              ))}
            </div>
          )}
          {placed.length ? (
            <p className="caption">
              برای جابه‌جایی یا بازگرداندن یک شیء، روی آن ضربه بزنید.
            </p>
          ) : null}
        </Card>

        {stored.length ? (
          <Card className="stack">
            <div className="eyebrow">انبار باغ</div>
            <div className="cluster" aria-label="اشیای ذخیره‌شده">
              {stored.map((object) => (
                <GardenObject
                  key={object.id}
                  label={object.object_key}
                  placed={false}
                  onClick={() => setPlacing(object)}
                />
              ))}
            </div>
          </Card>
        ) : null}

        {managing ? (
          <PlacedObjectActions
            object={managing}
            onClose={() => setManaging(null)}
            onMove={() => {
              setPlacing(managing);
              setManaging(null);
            }}
            onReturn={() => returnMutation.mutate(managing.id)}
            returnError={
              returnMutation.isError ? errorText(returnMutation.error) : null
            }
            returning={returnMutation.isPending}
          />
        ) : null}

        {placing ? (
          <PlacementSheet
            object={placing}
            onClose={() => setPlacing(null)}
            quadrant={unlockedQuadrant}
          />
        ) : null}
      </div>
    </AppShell>
  );
}
