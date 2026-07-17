"use client";

import { useMemo, useState } from "react";
import {
  Banner,
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

export function TodayDashboard({
  context,
  policy,
  today,
  journeyOffers,
  activePetId,
  onPetSelect,
  loading,
}: {
  context: MeContextResponse;
  policy: PolicyResponse;
  today: TodayResponse | null;
  journeyOffers: JourneyOfferResponse[];
  activePetId: string;
  onPetSelect: (petId: string) => void;
  loading?: boolean;
}) {
  const activePet = context.pets.find((pet) => pet.id === activePetId);

  if (!isPolicyCompatible(policy)) {
    return (
      <ErrorState
        title="سیاست runtime ناسازگار است"
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
          <div className="eyebrow">Pet Platform</div>
          <h1 className="display">امروز</h1>
        </div>
        <span className="chip chip--active">RTL</span>
      </div>

      <PetSwitcher
        pets={context.pets}
        activePetId={activePetId}
        onSelect={onPetSelect}
      />

      {loading || !today ? (
        <Card className="stack">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </Card>
      ) : (
        <>
          <FoodStatusCard today={today} policy={policy} />
          <NextEventCard today={today} />
          <HouseholdInventoryBoundary today={today} />
          {shouldRenderCareJourneys(policy, journeyOffers) ? (
            <CareJourneyPreview offers={journeyOffers} />
          ) : null}
          {shouldRenderReserveNow(policy) ? (
            <Banner tone="warning">
              رزرو اکنون فقط با سیاست فعال نمایش داده می‌شود.
            </Banner>
          ) : null}
          <GardenPreview today={today} />
        </>
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
          سهم مصرف فقط پس از setup و تأیید باز شدن بسته به پت نسبت داده می‌شود.
        </p>
      </div>
    </Card>
  );
}

function CareJourneyPreview({ offers }: { offers: JourneyOfferResponse[] }) {
  return (
    <Card className="stack" data-testid="care-journeys">
      <div className="eyebrow">مسیر مراقبتی</div>
      <h2 className="title">{offers[0]?.title_fa}</h2>
      <p className="caption">
        فقط مسیرهای تأییدشده، فعال، واجد شرایط و دارای مرجع حرفه‌ای از backend
        نمایش داده می‌شوند.
      </p>
    </Card>
  );
}

function GardenPreview({ today }: { today: TodayResponse }) {
  return (
    <section
      className="garden-preview stack"
      id="garden"
      data-testid="garden-preview"
    >
      <div className="split">
        <div>
          <div className="eyebrow" style={{ color: "oklch(0.8 0.03 150)" }}>
            باغ ایرانی
          </div>
          <h2 className="title">باغ {today.pet.name}</h2>
          <p className="caption" style={{ color: "oklch(0.8 0.03 150)" }}>
            {formatPersianNumber(today.garden.object_count)} شیء جای‌گذاری‌شده
            از خاطره‌های معتبر
          </p>
        </div>
        <div className="garden-mark" aria-hidden="true" />
      </div>
    </section>
  );
}

export function useFixtureSelectedPet(context: MeContextResponse) {
  const [activePetId, setActivePetId] = useState(context.pets[0]?.id ?? "");
  const activePet = useMemo(
    () => context.pets.find((pet) => pet.id === activePetId) ?? context.pets[0],
    [activePetId, context.pets],
  );
  return { activePet, activePetId, setActivePetId };
}
