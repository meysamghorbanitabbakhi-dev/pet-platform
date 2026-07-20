"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import type { ConciergeOfferResponse } from "@/lib/api-types";
import {
  acceptConciergeOffer,
  declineConciergeOffer,
  getCustomerRequest,
  getPolicies,
  listAddresses,
  listConciergeOffers,
  refreshConciergeOffer,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatIranDateTime } from "@/lib/format";
import { shouldRenderConciergeOffers } from "@/lib/policy";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";
import {
  offerStatusLabel,
  offerStatusTone,
  promiseLabel,
  requestStatusLabel,
  requestStatusTone,
  requestTypeLabel,
} from "./labels";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

export function ConciergeRequestDetail({ requestId }: { requestId: string }) {
  const requestQuery = useQuery({
    queryKey: ["customer-requests", requestId],
    queryFn: () => getCustomerRequest(requestId),
    enabled: Boolean(requestId),
  });
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });

  const sessionExpired = useSessionExpiryRedirect(requestQuery.error);

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

  if (requestQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (requestQuery.isError || !requestQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="این درخواست در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void requestQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  const request = requestQuery.data;
  const unmetPromises = Object.entries(request.promises).filter(
    ([, value]) => value === false,
  );

  return (
    <AppShell>
      <div className="stack">
        <div className="split">
          <div>
            <div className="eyebrow">پشتیبانی</div>
            <h1 className="display">
              {requestTypeLabel(request.request_type)}
            </h1>
          </div>
          <StatusChip tone={requestStatusTone(request.status)}>
            {requestStatusLabel(request.status)}
          </StatusChip>
        </div>

        <Card className="stack">
          <p>{request.message_fa}</p>
          <span className="caption">
            ثبت‌شده در {formatIranDateTime(request.created_at)}
          </span>
        </Card>

        {request.request_type === "concierge_sourcing" &&
        shouldRenderConciergeOffers(policyQuery.data) ? (
          <ConciergeOfferSection
            requestId={request.id}
            householdId={request.household_id}
          />
        ) : null}

        <Card className="stack">
          <div className="eyebrow">اعلامیه</div>
          <p className="caption">{request.acknowledgement_fa}</p>
          {unmetPromises.length ? (
            <ul className="stack">
              {unmetPromises.map(([key]) => (
                <li className="caption" key={key}>
                  این درخواست {promiseLabel(key)} نیست.
                </li>
              ))}
            </ul>
          ) : null}
        </Card>
      </div>
    </AppShell>
  );
}

function ConciergeOfferSection({
  requestId,
  householdId,
}: {
  requestId: string;
  householdId: string;
}) {
  const offersQuery = useQuery({
    queryKey: ["customer-requests", requestId, "concierge-offers"],
    queryFn: () => listConciergeOffers(requestId),
    enabled: Boolean(requestId),
  });

  if (offersQuery.isLoading) {
    return (
      <Card className="stack">
        <Skeleton />
      </Card>
    );
  }

  if (offersQuery.isError) {
    return (
      <Card className="stack">
        <Banner tone="error">{errorText(offersQuery.error)}</Banner>
        <Button variant="secondary" onClick={() => void offersQuery.refetch()}>
          تلاش دوباره
        </Button>
      </Card>
    );
  }

  const offers = offersQuery.data ?? [];
  if (!offers.length) return null;
  // The backend orders offer cycles created_at desc, so the first item is
  // always the current/most-recent cycle -- older ones (e.g. before a
  // refresh) are history, not shown here.
  const latest = offers[0];

  return (
    <ConciergeOfferCard
      offer={latest}
      requestId={requestId}
      householdId={householdId}
    />
  );
}

function ConciergeOfferCard({
  offer,
  requestId,
  householdId,
}: {
  offer: ConciergeOfferResponse;
  requestId: string;
  householdId: string;
}) {
  const queryClient = useQueryClient();
  const [sheet, setSheet] = useState<"accept" | "decline" | null>(null);

  async function invalidate() {
    setSheet(null);
    await queryClient.invalidateQueries({
      queryKey: ["customer-requests", requestId, "concierge-offers"],
    });
  }

  const refreshMutation = useMutation({
    mutationFn: () => refreshConciergeOffer(offer.id),
    onSuccess: invalidate,
  });

  return (
    <Card className="stack" data-testid="concierge-offer-card">
      <div className="split">
        <h2 className="title">پیشنهاد تامین محصول</h2>
        <StatusChip tone={offerStatusTone(offer.status)}>
          {offerStatusLabel(offer.status)}
        </StatusChip>
      </div>

      {offer.status === "offer_presented" ? (
        <>
          <div className="split">
            <span>{offer.title_fa}</span>
            <Money irr={offer.price_irr} />
          </div>
          {offer.pricing_mode === "reference_price_savings" &&
          offer.reference_price_irr ? (
            <p className="caption">
              قیمت مرجع بازار: <Money irr={offer.reference_price_irr} />
            </p>
          ) : null}
          <p className="caption">{offer.price_explanation_fa}</p>
          <div className="grid grid--two">
            {offer.supplier_country_code ? (
              <div>
                <div className="eyebrow">کشور تامین‌کننده</div>
                <div>{offer.supplier_country_code}</div>
              </div>
            ) : null}
            {offer.minimum_shelf_life_months ? (
              <div>
                <div className="eyebrow">حداقل تاریخ انقضا</div>
                <div>{offer.minimum_shelf_life_months} ماه</div>
              </div>
            ) : null}
            {offer.estimated_delivery_days ? (
              <div>
                <div className="eyebrow">زمان تقریبی تحویل</div>
                <div>{offer.estimated_delivery_days} روز</div>
              </div>
            ) : null}
          </div>
          {offer.expires_at ? (
            <p className="caption">
              مهلت پاسخ: {formatIranDateTime(offer.expires_at)}
            </p>
          ) : null}
          <div className="cluster">
            <Button onClick={() => setSheet("accept")}>پذیرش پیشنهاد</Button>
            <Button variant="ghost" onClick={() => setSheet("decline")}>
              رد پیشنهاد
            </Button>
          </div>
        </>
      ) : null}

      {offer.status === "expired" ? (
        <>
          <p className="caption">
            می‌توانید درخواست بررسی دوباره ثبت کنید؛ بررسی و قیمت جدید ممکن است
            متفاوت باشد و بررسی خودکار انجام نمی‌شود.
          </p>
          {refreshMutation.isError ? (
            <Banner tone="error">{errorText(refreshMutation.error)}</Banner>
          ) : null}
          <Button
            variant="secondary"
            loading={refreshMutation.isPending}
            onClick={() => refreshMutation.mutate()}
          >
            درخواست بررسی دوباره
          </Button>
        </>
      ) : null}

      {offer.status === "unavailable" && offer.unavailable_reason ? (
        <p className="caption">{offer.unavailable_reason}</p>
      ) : null}
      {offer.status === "declined" && offer.decline_reason ? (
        <p className="caption">{offer.decline_reason}</p>
      ) : null}
      {offer.status === "accepted" ? (
        <p className="caption">
          سفارش شما ثبت شد؛ پرداخت مبلغ همچنان نیاز به تایید صریح شماست و
          به‌صورت خودکار انجام نشده است.
        </p>
      ) : null}

      {sheet === "accept" ? (
        <AcceptOfferSheet
          offerId={offer.id}
          householdId={householdId}
          onClose={() => setSheet(null)}
          onAccepted={invalidate}
        />
      ) : null}
      {sheet === "decline" ? (
        <DeclineOfferSheet
          offerId={offer.id}
          onClose={() => setSheet(null)}
          onDeclined={invalidate}
        />
      ) : null}
    </Card>
  );
}

function AcceptOfferSheet({
  offerId,
  householdId,
  onClose,
  onAccepted,
}: {
  offerId: string;
  householdId: string;
  onClose: () => void;
  onAccepted: () => void;
}) {
  const addressesQuery = useQuery({
    queryKey: ["households", householdId, "addresses"],
    queryFn: () => listAddresses(householdId),
  });
  const acceptMutation = useMutation({
    mutationFn: (addressId: string) =>
      acceptConciergeOffer(offerId, { address_id: addressId }),
    onSuccess: onAccepted,
  });

  return (
    <Sheet title="پذیرش پیشنهاد" onClose={onClose}>
      <div className="stack">
        <p className="caption">
          با پذیرش، سفارشی با همین قیمت ثبت می‌شود؛ پرداخت جداگانه و با تایید
          صریح شما انجام می‌شود و هیچ مبلغی به‌صورت خودکار برداشت نمی‌شود. آدرس
          تحویل را انتخاب کنید.
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
                loading={acceptMutation.isPending}
                disabled={acceptMutation.isPending}
                onClick={() => acceptMutation.mutate(address.id)}
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
        {acceptMutation.isError ? (
          <Banner tone="error">{errorText(acceptMutation.error)}</Banner>
        ) : null}
      </div>
    </Sheet>
  );
}

function DeclineOfferSheet({
  offerId,
  onClose,
  onDeclined,
}: {
  offerId: string;
  onClose: () => void;
  onDeclined: () => void;
}) {
  const [reason, setReason] = useState("");
  const declineMutation = useMutation({
    mutationFn: () =>
      declineConciergeOffer(offerId, { reason: reason.trim() || null }),
    onSuccess: onDeclined,
  });

  return (
    <Sheet title="رد پیشنهاد" onClose={onClose}>
      <div className="stack">
        <div className="field">
          <label htmlFor="concierge-decline-reason">دلیل رد (اختیاری)</label>
          <textarea
            id="concierge-decline-reason"
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
            تایید رد پیشنهاد
          </Button>
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
