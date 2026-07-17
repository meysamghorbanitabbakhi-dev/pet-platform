"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PetSwitcher,
  Skeleton,
} from "@/components/primitives";
import type {
  JourneyOfferResponse,
  MeContextResponse,
  PolicyResponse,
  TodayResponse,
} from "@/lib/api-types";
import { formatPersianNumber } from "@/lib/format";
import {
  isPolicyCompatible,
  shouldRenderCareJourneys,
  shouldRenderReserveNow,
} from "@/lib/policy";
import { FoodStatusCard, NextEventCard } from "./food-status";

const selectedPetKey = "pet-platform.selected-pet-id";

export function TodayDashboard({
  context,
  policy,
  today,
  journeyOffers,
  activePetId,
  onPetSelect,
  loading,
  todayError,
  onTodayRetry,
  journeyError,
  onJourneyRetry,
}: {
  context: MeContextResponse;
  policy: PolicyResponse;
  today: TodayResponse | null;
  journeyOffers: JourneyOfferResponse[];
  activePetId: string;
  onPetSelect: (petId: string) => void;
  loading?: boolean;
  todayError?: boolean;
  onTodayRetry?: () => void;
  journeyError?: boolean;
  onJourneyRetry?: () => void;
}) {
  const activePet = context.pets.find((pet) => pet.id === activePetId);

  if (!isPolicyCompatible(policy)) {
    return (
      <ErrorState
        title="سیاست اجرا ناسازگار است"
        body="نمایش وضعیت پت تا دریافت سیاست معتبر متوقف شد."
      />
    );
  }

  if (!activePet) {
    return (
      <EmptyState
        title="پتی برای نمایش وجود ندارد"
        body="فروشگاه همچنان در دسترس است و می‌توانید پروفایل پت را بعداً کامل کنید."
      />
    );
  }

  return (
    <div className="stack" data-testid="today-dashboard">
      <div className="split">
        <div>
          <div className="eyebrow">وضعیت جاری</div>
          <h1 className="display">امروز</h1>
        </div>
      </div>

      <PetSwitcher
        pets={context.pets}
        activePetId={activePetId}
        onSelect={onPetSelect}
      />

      {loading ? (
        <Card className="stack">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </Card>
      ) : todayError ? (
        <ErrorState
          title="وضعیت امروز این پت دریافت نشد"
          body="بخش‌های دیگر صفحه باقی می‌مانند؛ فقط این ماژول دوباره دریافت می‌شود."
          action={
            onTodayRetry ? (
              <Button variant="secondary" onClick={onTodayRetry}>
                تلاش دوباره
              </Button>
            ) : null
          }
        />
      ) : today ? (
        <>
          <FoodStatusCard today={today} policy={policy} />
          <NextEventCard today={today} />
          <HouseholdInventoryBoundary today={today} />
          {journeyError ? (
            <Banner tone="warning">
              مسیرهای مراقبتی دریافت نشدند.
              {onJourneyRetry ? (
                <Button variant="ghost" onClick={onJourneyRetry}>
                  تلاش دوباره
                </Button>
              ) : null}
            </Banner>
          ) : shouldRenderCareJourneys(policy, journeyOffers) ? (
            <CareJourneyPreview offers={journeyOffers} />
          ) : null}
          {shouldRenderReserveNow(policy) ? (
            <Banner tone="warning">
              رزرو اکنون فقط با سیاست فعال نمایش داده می‌شود.
            </Banner>
          ) : null}
          <GardenPreview today={today} />
        </>
      ) : (
        <EmptyState
          title="وضعیت امروز آماده نیست"
          body="وقتی سرویس داده معتبر برگرداند، این بخش نمایش داده می‌شود."
        />
      )}
    </div>
  );
}

function HouseholdInventoryBoundary({ today }: { today: TodayResponse }) {
  const itemLabel = "label" in today.food ? today.food.label : "غذای ثبت نشده";
  return (
    <Card className="grid grid--two" data-testid="inventory-boundary">
      <div>
        <div className="eyebrow">انبار خانوار</div>
        <h2 className="title">{itemLabel}</h2>
        <p className="caption">واحد فیزیکی غذا متعلق به خانوار است.</p>
      </div>
      <div>
        <div className="eyebrow">مصرف پت</div>
        <h2 className="title">{today.pet.name}</h2>
        <p className="caption">
          سهم مصرف فقط پس از آماده‌سازی و تایید باز شدن بسته به پت نسبت داده
          می‌شود.
        </p>
      </div>
    </Card>
  );
}

function CareJourneyPreview({ offers }: { offers: JourneyOfferResponse[] }) {
  return (
    <Link className="card stack" data-testid="care-journeys" href="/journeys">
      <div className="eyebrow">مسیر مراقبتی</div>
      <h2 className="title">{offers[0]?.title_fa}</h2>
      <p className="caption">
        فقط مسیرهایی نمایش داده می‌شوند که سرویس به عنوان فعال، تاییدشده و واجد
        شرایط برگردانده است.
      </p>
    </Link>
  );
}

function GardenPreview({ today }: { today: TodayResponse }) {
  return (
    <Link
      className="garden-preview stack"
      id="garden"
      data-testid="garden-preview"
      href={`/garden/${today.pet.id}`}
    >
      <div className="split">
        <div>
          <div className="eyebrow garden-preview__eyebrow">باغ ایرانی</div>
          <h2 className="title">باغ {today.pet.name}</h2>
          <p className="caption garden-preview__caption">
            {formatPersianNumber(today.garden.object_count)} شیء جای‌گذاری‌شده
            از خاطره‌های معتبر
          </p>
        </div>
        <div className="garden-mark" aria-hidden="true" />
      </div>
    </Link>
  );
}

export function usePersistedSelectedPet(context: MeContextResponse) {
  const fallbackPetId = context.pets[0]?.id ?? "";
  const [storedPetId, setStoredPetId] = useState(() =>
    typeof window === "undefined"
      ? null
      : window.localStorage.getItem(selectedPetKey),
  );
  const activePetId =
    storedPetId && context.pets.some((pet) => pet.id === storedPetId)
      ? storedPetId
      : fallbackPetId;

  const setActivePetId = (petId: string) => {
    setStoredPetId(petId);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(selectedPetKey, petId);
    }
  };

  const activePet = useMemo(
    () => context.pets.find((pet) => pet.id === activePetId) ?? context.pets[0],
    [activePetId, context.pets],
  );
  return { activePet, activePetId, setActivePetId };
}
