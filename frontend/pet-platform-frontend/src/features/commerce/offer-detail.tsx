import Link from "next/link";
import { Banner, Card } from "@/components/primitives";
import type { OfferDetailResponse, PolicyResponse } from "@/lib/api-types";
import {
  authenticityLabel,
  availabilityLabel,
  supplierCountryLabel,
} from "@/lib/commerce-format";
import {
  formatIranDate,
  formatPercent,
  formatPersianNumber,
  formatTomanFromIrr,
} from "@/lib/format";
import { AddToCartButton } from "./add-to-cart-button";
import { AvailabilitySubscribe } from "./availability-subscribe";

export function OfferDetail({
  offer,
  policy,
}: {
  offer: OfferDetailResponse;
  policy: Pick<PolicyResponse, "irr_per_customer_display_unit">;
}) {
  const unavailable = offer.availability !== "available";
  const primaryMedia = [...offer.media].sort(
    (a, b) => a.sort_order - b.sort_order,
  )[0];

  return (
    <div className="stack">
      <div className="split">
        <div>
          <div className="eyebrow">جزئیات محصول</div>
          <h1 className="display">{offer.title_fa}</h1>
        </div>
        <Link className="button button--secondary" href="/cart">
          سبد خرید
        </Link>
      </div>

      <div className="offer-detail-layout">
        <Card className="stack">
          {primaryMedia ? (
            primaryMedia.media_type === "image" ? (
              // Product media references are controlled by the backend catalog.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className="product-media"
                src={primaryMedia.public_reference}
                alt={primaryMedia.alt_text_fa}
              />
            ) : (
              <video
                className="product-media"
                src={primaryMedia.public_reference}
                aria-label={primaryMedia.alt_text_fa}
                controls
              />
            )
          ) : (
            <div className="product-media product-media--empty">
              تصویر محصول از سرویس دریافت نشد
            </div>
          )}
        </Card>

        <Card className="stack">
          {unavailable ? (
            <>
              <Banner tone="warning">
                این محصول فعلا برای پرداخت کامل در دسترس نیست و وارد فرآیند
                پرداخت نمی‌شود.
              </Banner>
              <AvailabilitySubscribe offerId={offer.id} />
            </>
          ) : null}
          <div>
            <div className="money">
              {formatTomanFromIrr(
                offer.price_irr,
                policy.irr_per_customer_display_unit,
              )}
            </div>
            <p className="caption">مبلغ سرویس به ریال ذخیره شده است.</p>
          </div>
          <div className="grid grid--two">
            <Fact label="وضعیت" value={availabilityLabel(offer.availability)} />
            <Fact
              label="کشور تامین‌کننده"
              value={supplierCountryLabel(offer.supplier_country_code)}
            />
            <Fact label="اصالت" value={authenticityLabel(offer.authenticity)} />
            <Fact
              label="حداقل ماندگاری تحویل"
              value={`${formatPersianNumber(
                offer.minimum_shelf_life_months_at_delivery,
              )} ماه`}
            />
            <Fact
              label="تاریخ بررسی قیمت مرجع"
              value={formatIranDate(offer.reference_price_reviewed_at)}
            />
            <Fact
              label="صرفه‌جویی اعلام‌شده سرویس"
              value={formatPercent(offer.saving_percent)}
            />
          </div>
          {offer.description_fa ? (
            <p className="caption">{offer.description_fa}</p>
          ) : null}
          <div className="cluster">
            <AddToCartButton disabled={unavailable} offerId={offer.id} />
            <Link className="button button--secondary" href="/cart">
              مشاهده سبد
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="title">{value}</div>
    </div>
  );
}
