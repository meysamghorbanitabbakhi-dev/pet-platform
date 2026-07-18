"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { getOfferDetail, getPolicies } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  authenticityLabel,
  availabilityLabel,
  supplierCountryLabel,
} from "@/lib/commerce-format";
import { clearCompareList, toggleCompareItem } from "@/lib/compare-list";
import { formatPersianNumber, formatTomanFromIrr } from "@/lib/format";
import { useCompareListSnapshot } from "./use-compare-list";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

export function OfferCompare({ offerId }: { offerId: string }) {
  const compareList = useCompareListSnapshot();
  const offerIds = [offerId, ...compareList.filter((id) => id !== offerId)];

  const comparable = offerIds.length >= 2;
  const policyQuery = useQuery({
    queryKey: ["policy"],
    queryFn: getPolicies,
    enabled: comparable,
  });
  const offerQueries = useQueries({
    queries: offerIds.map((id) => ({
      queryKey: ["compare-offer", id],
      queryFn: () => getOfferDetail(id),
      enabled: comparable,
    })),
  });

  if (offerIds.length < 2) {
    return (
      <EmptyState
        title="محصولی برای مقایسه انتخاب نشده است"
        body="از صفحه جزئیات هر محصول، آن را به مقایسه اضافه کنید تا اینجا کنار هم نمایش داده شوند."
        action={
          <Link className="button button--primary" href="/shop">
            بازگشت به فروشگاه
          </Link>
        }
      />
    );
  }

  const loading =
    policyQuery.isLoading || offerQueries.some((query) => query.isLoading);
  const policy = policyQuery.data;

  return (
    <div className="stack">
      <div className="split">
        <div>
          <div className="eyebrow">فروشگاه</div>
          <h1 className="display">مقایسه محصول</h1>
        </div>
        <Button variant="ghost" onClick={() => clearCompareList()}>
          پاک کردن مقایسه
        </Button>
      </div>

      {loading ? (
        <div className="grid grid--two">
          {offerIds.map((id) => (
            <Card key={id} className="stack">
              <Skeleton />
              <Skeleton />
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid grid--two">
          {offerIds.map((id, index) => {
            const query = offerQueries[index];
            if (query.isError || !query.data) {
              return (
                <ErrorState
                  key={id}
                  title="این محصول دریافت نشد"
                  body={errorText(query.error)}
                />
              );
            }
            const offer = query.data;
            return (
              <Card key={id} className="stack">
                <h2 className="title">{offer.title_fa}</h2>
                {policy ? (
                  <div className="money">
                    {formatTomanFromIrr(
                      offer.price_irr,
                      policy.irr_per_customer_display_unit,
                    )}
                  </div>
                ) : null}
                <div className="stack">
                  <Fact
                    label="وضعیت"
                    value={availabilityLabel(offer.availability)}
                  />
                  <Fact
                    label="اصالت"
                    value={authenticityLabel(offer.authenticity)}
                  />
                  <Fact
                    label="کشور تامین‌کننده"
                    value={supplierCountryLabel(offer.supplier_country_code)}
                  />
                  <Fact
                    label="حداقل ماندگاری تحویل"
                    value={`${formatPersianNumber(
                      offer.minimum_shelf_life_months_at_delivery,
                    )} ماه`}
                  />
                </div>
                <div className="cluster">
                  <Link
                    className="button button--secondary"
                    href={`/shop/offer/${offer.id}`}
                  >
                    مشاهده جزئیات
                  </Link>
                  {compareList.includes(id) ? (
                    <Button
                      variant="ghost"
                      onClick={() => toggleCompareItem(id)}
                    >
                      حذف از مقایسه
                    </Button>
                  ) : null}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="split">
      <span className="caption">{label}</span>
      <span>{value}</span>
    </div>
  );
}
