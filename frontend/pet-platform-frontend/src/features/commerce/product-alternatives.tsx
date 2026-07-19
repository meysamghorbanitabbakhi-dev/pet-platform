"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import type { PolicyResponse } from "@/lib/api-types";
import { listProductAlternatives } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { supplierCountryLabel } from "@/lib/commerce-format";
import { formatTomanFromIrr } from "@/lib/format";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در دریافت جایگزین‌های پیشنهادی.";
}

export function ProductAlternatives({
  productId,
  policy,
}: {
  productId: string;
  policy: Pick<PolicyResponse, "irr_per_customer_display_unit">;
}) {
  const query = useQuery({
    queryKey: ["product-alternatives", productId],
    queryFn: () => listProductAlternatives(productId),
  });

  return (
    <Card className="stack">
      <div>
        <h2 className="title">جایگزین‌های پیشنهادی پلتفرم</h2>
        <p className="caption">
          این موارد جایگزین‌هایی هستند که اپراتور پلتفرم به‌صورت دستی انتخاب
          کرده است، نه جایگزین تضمین‌شده بالینی یا تغذیه‌ای. پیش از تغییر رژیم
          غذایی پت با دامپزشک مشورت کنید.
        </p>
      </div>
      {query.isLoading ? (
        <Skeleton label="در حال بارگذاری جایگزین‌ها" />
      ) : query.isError ? (
        <ErrorState
          title="جایگزین‌ها دریافت نشد"
          body={errorText(query.error)}
          action={
            <button
              type="button"
              className="button button--secondary"
              onClick={() => query.refetch()}
            >
              تلاش مجدد
            </button>
          }
        />
      ) : !query.data || query.data.length === 0 ? (
        <EmptyState
          title="در حال حاضر جایگزینی ثبت نشده است"
          body="اپراتور پلتفرم هنوز جایگزینی برای این محصول تایید نکرده است."
        />
      ) : (
        <div className="stack">
          {query.data.map((alternative) => (
            <Card key={alternative.id} className="stack">
              <div className="split">
                <Link
                  className="title"
                  href={`/shop/offer/${alternative.offer.id}`}
                >
                  {alternative.offer.title_fa}
                </Link>
                <span className="chip">
                  {supplierCountryLabel(alternative.offer.supplier_country)}
                </span>
              </div>
              <div className="money">
                {formatTomanFromIrr(
                  alternative.offer.price_irr,
                  policy.irr_per_customer_display_unit,
                )}
              </div>
              <p className="caption">{alternative.rationale_fa}</p>
              {alternative.compatibility_notes_fa ? (
                <p className="caption">{alternative.compatibility_notes_fa}</p>
              ) : null}
              <Link
                className="button button--secondary"
                href={`/shop/offer/${alternative.offer.id}`}
              >
                مشاهده جزئیات
              </Link>
            </Card>
          ))}
        </div>
      )}
    </Card>
  );
}
