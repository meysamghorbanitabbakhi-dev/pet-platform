"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Money,
  Sheet,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import type {
  InventoryAssignmentResponse,
  OpenInventoryBody,
  ReorderAssessmentResponse,
} from "@/lib/api-types";
import {
  approveReplenishmentReservation,
  assessReorder,
  correctEstimate,
  declineReplenishmentReservation,
  exhaustInventory,
  getInventoryDetail,
  getOfferDetail,
  getPolicies,
  listAddresses,
  listReplenishmentReservations,
  openInventory,
  snoozeReorder,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatIranDateTime, formatPersianNumber } from "@/lib/format";
import { enabled, shouldRenderReplenishmentReservations } from "@/lib/policy";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";

const levelLabels: Record<string, string> = {
  full: "پر (۷۵ تا ۱۰۰٪)",
  more_than_half: "بیشتر از نصف (۵۰ تا ۷۵٪)",
  less_than_half: "کمتر از نصف (۲۵ تا ۵۰٪)",
  near_empty: "تقریباً تمام‌شده (کمتر از ۲۵٪)",
};

const levelOrder = [
  "full",
  "more_than_half",
  "less_than_half",
  "near_empty",
] as const;

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

function RemainingChooser({
  levelEstimationEnabled,
  submitting,
  submitError,
  onSubmit,
}: {
  levelEstimationEnabled: boolean;
  submitting: boolean;
  submitError: string | null;
  onSubmit: (body: OpenInventoryBody) => void;
}) {
  const [mode, setMode] = useState<"grams" | "level" | "unknown">("unknown");
  const [grams, setGrams] = useState("");
  const [level, setLevel] = useState<(typeof levelOrder)[number] | null>(null);

  function submit() {
    if (mode === "grams") {
      const parsed = Number.parseInt(grams, 10);
      if (!Number.isFinite(parsed) || parsed <= 0) return;
      onSubmit({
        feeding_context: "unknown",
        remaining: { mode: "grams", grams: parsed },
      });
      return;
    }
    if (mode === "level") {
      if (!level) return;
      onSubmit({
        feeding_context: "unknown",
        remaining: { mode: "level", level },
      });
      return;
    }
    onSubmit({
      feeding_context: "unknown",
      remaining: null,
      remaining_grams: null,
    });
  }

  const canSubmit =
    mode === "unknown" ||
    (mode === "grams" && Number.parseInt(grams, 10) > 0) ||
    (mode === "level" && level !== null);

  return (
    <div className="stack">
      <div
        className="cluster"
        role="radiogroup"
        aria-label="نحوه ثبت باقی‌مانده"
      >
        <Button
          type="button"
          variant={mode === "grams" ? "selection" : "secondary"}
          aria-pressed={mode === "grams"}
          onClick={() => setMode("grams")}
        >
          دقیقاً می‌دانم (گرم)
        </Button>
        {levelEstimationEnabled ? (
          <Button
            type="button"
            variant={mode === "level" ? "selection" : "secondary"}
            aria-pressed={mode === "level"}
            onClick={() => setMode("level")}
          >
            تقریباً می‌دانم (سطح)
          </Button>
        ) : null}
        <Button
          type="button"
          variant={mode === "unknown" ? "selection" : "secondary"}
          aria-pressed={mode === "unknown"}
          onClick={() => setMode("unknown")}
        >
          نمی‌دانم
        </Button>
      </div>

      {mode === "grams" ? (
        <div className="field">
          <label htmlFor="remaining-grams">گرم باقی‌مانده</label>
          <input
            id="remaining-grams"
            className="input"
            inputMode="numeric"
            type="number"
            min={1}
            value={grams}
            onChange={(event) => setGrams(event.target.value)}
          />
        </div>
      ) : null}

      {mode === "level" ? (
        <div
          className="cluster"
          role="radiogroup"
          aria-label="سطح تقریبی باقی‌مانده"
        >
          {levelOrder.map((value) => (
            <Button
              key={value}
              type="button"
              variant={level === value ? "selection" : "secondary"}
              aria-pressed={level === value}
              onClick={() => setLevel(value)}
            >
              {levelLabels[value]}
            </Button>
          ))}
        </div>
      ) : null}

      {mode === "unknown" ? (
        <p className="caption">
          بدون ثبت مقدار، سهم هر پت نامشخص می‌ماند و عددی برای مصرف نمایش داده
          نمی‌شود تا داده کافی به‌دست آید.
        </p>
      ) : null}

      {submitError ? <Banner tone="error">{submitError}</Banner> : null}

      <Button
        onClick={submit}
        disabled={!canSubmit || submitting}
        loading={submitting}
      >
        ثبت
      </Button>
    </div>
  );
}

function AssignmentsSummary({
  assignments,
  sharesKnown,
}: {
  assignments: InventoryAssignmentResponse[];
  sharesKnown: boolean;
}) {
  if (assignments.length === 0) {
    return (
      <p className="caption">
        این واحد هنوز به پت خاصی اختصاص داده نشده و به‌صورت سهم خانوار در نظر
        گرفته می‌شود.
      </p>
    );
  }
  return (
    <div className="stack">
      <div className="eyebrow">اختصاص به پت‌ها</div>
      <ul className="stack" aria-label="فهرست اختصاص">
        {assignments.map((assignment) => (
          <li className="split" key={assignment.pet.id}>
            <span>{assignment.pet.name}</span>
            <span className="caption">
              {sharesKnown && assignment.share_basis_points
                ? `${Math.round(assignment.share_basis_points / 100)}٪ سهم`
                : "سهم نامشخص"}
            </span>
          </li>
        ))}
      </ul>
      {!sharesKnown ? (
        <p className="caption">
          سهم دقیق هر پت از این واحد نامشخص است؛ به همین دلیل عدد سرانه نمایش
          داده نمی‌شود.
        </p>
      ) : null}
    </div>
  );
}

const reorderOutcomeLabel: Record<string, string> = {
  insufficient_facts: "برای بررسی، اطلاعات کافی وجود ندارد.",
  not_yet: "موجودی فعلی هنوز کافی است.",
  order_now: "زمان سفارش مجدد رسیده است.",
  policy_blocked: "بررسی تجدید سفارش موقتاً در دسترس نیست.",
  snoozed: "بررسی تجدید سفارش به‌خواب رفته است.",
};

const reorderOutcomeTone: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  insufficient_facts: "muted",
  not_yet: "positive",
  order_now: "warning",
  policy_blocked: "muted",
  snoozed: "info",
};

function ReorderPanel({ unitId }: { unitId: string }) {
  const [assessment, setAssessment] =
    useState<ReorderAssessmentResponse | null>(null);
  const [showSnooze, setShowSnooze] = useState(false);

  const assessMutation = useMutation({
    mutationFn: () => assessReorder(unitId),
    onSuccess: (data) => setAssessment(data),
  });

  const snoozeMutation = useMutation({
    mutationFn: () => snoozeReorder(unitId, { hours: 72 }),
    onSuccess: async () => {
      setShowSnooze(false);
      await assessMutation.mutateAsync();
    },
  });

  return (
    <Card className="stack">
      <div className="split">
        <h2 className="title">ارزیابی تجدید سفارش</h2>
        <Button
          variant="secondary"
          onClick={() => assessMutation.mutate()}
          loading={assessMutation.isPending}
        >
          بررسی وضعیت
        </Button>
      </div>
      {assessMutation.isError ? (
        <Banner tone="error">{errorText(assessMutation.error)}</Banner>
      ) : null}
      {assessment ? (
        <div className="stack">
          <StatusChip tone={reorderOutcomeTone[assessment.outcome] ?? "muted"}>
            {reorderOutcomeLabel[assessment.outcome] ?? assessment.outcome}
          </StatusChip>
          <p className="caption">{assessment.recommendation}</p>
          {assessment.remaining_low_days !== null &&
          assessment.remaining_low_days !== undefined ? (
            <p className="caption">
              بازه برآورد باقی‌مانده:{" "}
              {formatPersianNumber(assessment.remaining_low_days)}
              {assessment.remaining_high_days
                ? ` تا ${formatPersianNumber(assessment.remaining_high_days)}`
                : ""}{" "}
              روز
            </p>
          ) : null}
          {assessment.outcome === "snoozed" && assessment.snoozed_until ? (
            <p className="caption">
              تا {formatIranDateTime(assessment.snoozed_until)} به‌خواب رفته
              است.
            </p>
          ) : null}
          {(assessment.outcome === "order_now" ||
            assessment.outcome === "not_yet") &&
          assessment.options?.length ? (
            <ul className="stack" aria-label="گزینه‌های تجدید سفارش">
              {assessment.options.map((option) => (
                <li className="split" key={option.offer_id}>
                  <span className="ltr-data">{option.sku}</span>
                  <StatusChip tone={option.available ? "positive" : "muted"}>
                    {option.available ? "موجود" : "ناموجود"}
                  </StatusChip>
                </li>
              ))}
            </ul>
          ) : null}
          {assessment.outcome === "order_now" ||
          assessment.outcome === "not_yet" ? (
            <Button variant="secondary" onClick={() => setShowSnooze(true)}>
              به‌خواب بردن تا ۷۲ ساعت
            </Button>
          ) : null}
        </div>
      ) : null}

      {showSnooze ? (
        <Sheet title="به‌خواب بردن بررسی" onClose={() => setShowSnooze(false)}>
          <div className="stack">
            <p className="caption">
              بررسی تجدید سفارش تا حداکثر ۷۲ ساعت متوقف می‌شود. در صورت بدتر شدن
              قابل‌توجه وضعیت، سرویس پیش از پایان این مدت دوباره هشدار می‌دهد.
            </p>
            {snoozeMutation.isError ? (
              <Banner tone="error">{errorText(snoozeMutation.error)}</Banner>
            ) : null}
            <div className="cluster">
              <Button
                loading={snoozeMutation.isPending}
                onClick={() => snoozeMutation.mutate()}
              >
                تایید به‌خواب بردن
              </Button>
              <Button variant="ghost" onClick={() => setShowSnooze(false)}>
                انصراف
              </Button>
            </div>
          </div>
        </Sheet>
      ) : null}
    </Card>
  );
}

const replenishmentStatusLabel: Record<string, string> = {
  pending_approval: "در انتظار تایید شما",
  approved: "تایید شد و سفارش ایجاد شد",
  declined: "رد شد",
  expired: "مهلت پاسخ به پایان رسید",
  invalidated: "به دلیل تغییر وضعیت این واحد، لغو شد",
};

const replenishmentStatusTone: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  pending_approval: "warning",
  approved: "positive",
  declined: "muted",
  expired: "muted",
  invalidated: "muted",
};

function ApproveReplenishmentSheet({
  reservationId,
  householdId,
  onClose,
  onApproved,
}: {
  reservationId: string;
  householdId: string;
  onClose: () => void;
  onApproved: () => void;
}) {
  const addressesQuery = useQuery({
    queryKey: ["households", householdId, "addresses"],
    queryFn: () => listAddresses(householdId),
  });
  const approveMutation = useMutation({
    mutationFn: (addressId: string) =>
      approveReplenishmentReservation(reservationId, {
        address_id: addressId,
      }),
    onSuccess: onApproved,
  });

  return (
    <Sheet title="تایید سفارش تمدید" onClose={onClose}>
      <div className="stack">
        <p className="caption">
          با تایید، سفارشی با قیمت لحظه‌ای پیشنهاد ثبت می‌شود؛ پرداخت جداگانه و
          با تایید صریح شما انجام می‌شود و هیچ مبلغی به‌صورت خودکار برداشت
          نمی‌شود. آدرس تحویل را انتخاب کنید.
        </p>
        {addressesQuery.isLoading ? <Skeleton /> : null}
        {addressesQuery.isError ? (
          <Banner tone="error">{errorText(addressesQuery.error)}</Banner>
        ) : null}
        {addressesQuery.data?.length ? (
          <div className="stack">
            {addressesQuery.data.map((address) => (
              <Button
                key={address.id}
                variant="secondary"
                loading={approveMutation.isPending}
                disabled={approveMutation.isPending}
                onClick={() => approveMutation.mutate(address.id)}
              >
                {address.label} · {address.recipient_name}
              </Button>
            ))}
          </div>
        ) : addressesQuery.isSuccess ? (
          <Banner tone="warning">
            آدرسی ثبت نشده است. ابتدا از بخش آدرس‌ها یک آدرس اضافه کنید.
          </Banner>
        ) : null}
        {approveMutation.isError ? (
          <Banner tone="error">{errorText(approveMutation.error)}</Banner>
        ) : null}
      </div>
    </Sheet>
  );
}

function DeclineReplenishmentSheet({
  reservationId,
  onClose,
  onDeclined,
}: {
  reservationId: string;
  onClose: () => void;
  onDeclined: () => void;
}) {
  const [reason, setReason] = useState("");
  const declineMutation = useMutation({
    mutationFn: () =>
      declineReplenishmentReservation(reservationId, {
        reason: reason.trim() || null,
      }),
    onSuccess: onDeclined,
  });

  return (
    <Sheet title="رد سفارش تمدید" onClose={onClose}>
      <div className="stack">
        <div className="field">
          <label htmlFor="replenishment-decline-reason">
            دلیل رد (اختیاری)
          </label>
          <textarea
            id="replenishment-decline-reason"
            className="input"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        {declineMutation.isError ? (
          <Banner tone="error">{errorText(declineMutation.error)}</Banner>
        ) : null}
        <div className="cluster">
          <Button
            loading={declineMutation.isPending}
            onClick={() => declineMutation.mutate()}
          >
            تایید رد سفارش
          </Button>
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
        </div>
      </div>
    </Sheet>
  );
}

function ReplenishmentReservationPanel({
  unitId,
  householdId,
}: {
  unitId: string;
  householdId: string;
}) {
  const queryClient = useQueryClient();
  const [sheet, setSheet] = useState<"approve" | "decline" | null>(null);

  const listQuery = useQuery({
    queryKey: ["pet-life", "replenishment-reservations", householdId],
    queryFn: () => listReplenishmentReservations(householdId),
    enabled: Boolean(householdId),
  });
  const reservationForOffer = (listQuery.data ?? []).find(
    (item) => item.inventory_unit_id === unitId,
  );
  const offerQuery = useQuery({
    queryKey: ["catalog", "offers", reservationForOffer?.offer_id],
    queryFn: () => getOfferDetail(reservationForOffer?.offer_id ?? ""),
    enabled: Boolean(reservationForOffer),
  });

  async function invalidate() {
    setSheet(null);
    await queryClient.invalidateQueries({
      queryKey: ["pet-life", "replenishment-reservations", householdId],
    });
  }

  if (listQuery.isLoading) {
    return (
      <Card className="stack">
        <Skeleton />
      </Card>
    );
  }

  if (listQuery.isError) {
    return (
      <Card className="stack">
        <Banner tone="error">{errorText(listQuery.error)}</Banner>
        <Button variant="secondary" onClick={() => void listQuery.refetch()}>
          تلاش دوباره
        </Button>
      </Card>
    );
  }

  const reservation = reservationForOffer;
  if (!reservation) return null;

  return (
    <Card className="stack">
      <div className="split">
        <h2 className="title">سفارش تمدید پیشنهادی</h2>
        <StatusChip
          tone={replenishmentStatusTone[reservation.status] ?? "muted"}
        >
          {replenishmentStatusLabel[reservation.status] ?? reservation.status}
        </StatusChip>
      </div>
      <p className="caption">
        بر اساس برآورد مصرف، این واحد ظرف{" "}
        {formatPersianNumber(reservation.predicted_depletion_low_days)} تا{" "}
        {formatPersianNumber(reservation.predicted_depletion_high_days)} روز
        تمام می‌شود. این فقط یک پیشنهاد است و بدون تایید صریح شما هیچ سفارش یا
        پرداختی ثبت نمی‌شود.
      </p>
      {offerQuery.data ? (
        <div className="split">
          <span>{offerQuery.data.title_fa}</span>
          <span>
            <Money irr={offerQuery.data.price_irr} /> (تقریبی)
          </span>
        </div>
      ) : offerQuery.isLoading ? (
        <Skeleton />
      ) : null}
      {reservation.status === "pending_approval" ? (
        <>
          <p className="caption">
            مهلت پاسخ: {formatIranDateTime(reservation.approval_expires_at)}
          </p>
          <div className="cluster">
            <Button onClick={() => setSheet("approve")}>تایید سفارش</Button>
            <Button variant="ghost" onClick={() => setSheet("decline")}>
              رد پیشنهاد
            </Button>
          </div>
        </>
      ) : null}
      {reservation.status === "approved" && reservation.resulting_order_id ? (
        <Link
          className="button button--secondary"
          href={`/orders/${reservation.resulting_order_id}`}
        >
          مشاهده سفارش
        </Link>
      ) : null}

      {sheet === "approve" ? (
        <ApproveReplenishmentSheet
          reservationId={reservation.id}
          householdId={householdId}
          onClose={() => setSheet(null)}
          onApproved={invalidate}
        />
      ) : null}
      {sheet === "decline" ? (
        <DeclineReplenishmentSheet
          reservationId={reservation.id}
          onClose={() => setSheet(null)}
          onDeclined={invalidate}
        />
      ) : null}
    </Card>
  );
}

export function InventoryOpening({ unitId }: { unitId: string }) {
  const queryClient = useQueryClient();
  const detailQuery = useQuery({
    queryKey: ["pet-life", "inventory", unitId],
    queryFn: () => getInventoryDetail(unitId),
    enabled: Boolean(unitId),
  });
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });

  async function invalidateInventory() {
    await queryClient.invalidateQueries({
      queryKey: ["pet-life", "inventory", unitId],
    });
    await queryClient.invalidateQueries({ queryKey: ["pet-life", "today"] });
  }

  const openMutation = useMutation({
    mutationFn: (body: OpenInventoryBody) => openInventory(unitId, body),
    onSuccess: () => invalidateInventory(),
  });

  const correctMutation = useMutation({
    mutationFn: (body: OpenInventoryBody) => correctEstimate(unitId, body),
    onSuccess: () => invalidateInventory(),
  });

  const exhaustMutation = useMutation({
    mutationFn: () => exhaustInventory(unitId),
    onSuccess: () => invalidateInventory(),
  });

  const sessionExpired = useSessionExpiryRedirect(detailQuery.error);

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

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
  const exhausted = detail.state === "exhausted";
  const levelEstimationEnabled = enabled(
    policyQuery.data,
    "semantic_level_estimation_enabled",
  );

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">انبار خانوار</div>
          <h1 className="display">{detail.label}</h1>
        </div>
        <Card className="stack">
          <div>
            <div className="eyebrow">شناسه واحد</div>
            <div className="ltr-data">{detail.id}</div>
          </div>
          <p className="caption">
            این واحد فیزیکی متعلق به خانوار است. مصرف پت پس از آماده‌سازی جدا
            ثبت می‌شود.
          </p>
          <AssignmentsSummary
            assignments={detail.assignments}
            sharesKnown={detail.shares_known}
          />
          {unavailable ? (
            <Banner tone="error">
              این واحد انبار برای باز کردن در دسترس نیست.
            </Banner>
          ) : exhausted ? (
            <Banner tone="info">
              این واحد به‌طور کامل مصرف شده است (exhausted).
            </Banner>
          ) : alreadyOpened ? (
            <>
              <Banner tone="info">
                باز شدن بسته قبلاً ثبت شده است. تخمین فقط از داده سرویس نمایش
                داده می‌شود.
              </Banner>
              <div className="stack">
                <h2 className="title">بهبود تخمین مصرف</h2>
                <RemainingChooser
                  levelEstimationEnabled={levelEstimationEnabled}
                  submitting={correctMutation.isPending}
                  submitError={
                    correctMutation.isError
                      ? errorText(correctMutation.error)
                      : null
                  }
                  onSubmit={(body) => correctMutation.mutate(body)}
                />
                {correctMutation.isSuccess ? (
                  <Banner tone="info">تخمین به‌روزرسانی شد.</Banner>
                ) : null}
              </div>
              <Button
                variant="secondary"
                onClick={() => exhaustMutation.mutate()}
                loading={exhaustMutation.isPending}
              >
                این واحد تمام شده است
              </Button>
              {exhaustMutation.isError ? (
                <Banner tone="error">{errorText(exhaustMutation.error)}</Banner>
              ) : null}
            </>
          ) : (
            <>
              <Banner tone="warning">
                تا قبل از تایید باز شدن بسته، تخمین روز باقی‌مانده شروع نمی‌شود.
              </Banner>
              <RemainingChooser
                levelEstimationEnabled={levelEstimationEnabled}
                submitting={openMutation.isPending}
                submitError={
                  openMutation.isError ? errorText(openMutation.error) : null
                }
                onSubmit={(body) => openMutation.mutate(body)}
              />
            </>
          )}
          {openMutation.isSuccess ? (
            <Banner tone="info">
              باز شدن بسته ثبت شد. اگر سرویس تخمین معتبر برگرداند، همان داده
              نمایش داده می‌شود.
            </Banner>
          ) : null}
        </Card>

        {alreadyOpened && !unavailable && !exhausted ? (
          <ReorderPanel unitId={unitId} />
        ) : null}
        {alreadyOpened &&
        !unavailable &&
        !exhausted &&
        shouldRenderReplenishmentReservations(policyQuery.data) ? (
          <ReplenishmentReservationPanel
            unitId={unitId}
            householdId={detail.household_id}
          />
        ) : null}
      </div>
    </AppShell>
  );
}
