"use client";

import { Button, Card, EmptyState } from "@/components/primitives";
import Link from "next/link";
import type { OfferListItem, PolicyResponse } from "@/lib/api-types";
import { addCartItem } from "@/lib/cart";
import { supplierCountryLabel } from "@/lib/commerce-format";
import { formatPersianNumber, formatTomanFromIrr } from "@/lib/format";

export function OfferList({
  offers,
  policy,
}: {
  offers: OfferListItem[];
  policy: Pick<PolicyResponse, "irr_per_customer_display_unit">;
}) {
  if (!offers.length) {
    return (
      <EmptyState
        title="محصولی برای نمایش وجود ندارد"
        body="فهرست فروشگاه پس از دریافت داده سرویس نمایش داده می‌شود."
      />
    );
  }

  return (
    <div className="grid grid--two">
      {offers.map((offer) => (
        <Card key={offer.id} className="stack">
          <div className="split">
            <div>
              <div className="eyebrow">
                کشور تامین‌کننده: {supplierCountryLabel(offer.supplier_country)}
              </div>
              <h2 className="title">
                <Link href={`/shop/offer/${offer.id}`}>{offer.title_fa}</Link>
              </h2>
            </div>
            <span className="chip chip--active">
              اصالت: تاییدشده توسط تامین‌کننده
            </span>
          </div>
          <div>
            <span className="money">
              {formatTomanFromIrr(
                offer.price_irr,
                policy.irr_per_customer_display_unit,
              ).replace(" تومان", "")}
            </span>{" "}
            <span className="money-unit">تومان</span>
          </div>
          <p className="caption">
            حداقل ماندگاری:{" "}
            {formatPersianNumber(offer.minimum_shelf_life_months)} ماه · واحد:{" "}
            {offer.unit_label_fa}
          </p>
          <div className="cluster">
            <Link
              className="button button--secondary"
              href={`/shop/offer/${offer.id}`}
            >
              جزئیات
            </Link>
            <Button variant="selection" onClick={() => addCartItem(offer.id)}>
              افزودن به سبد
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
