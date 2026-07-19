"use client";

import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { getOfferDetail } from "@/lib/api/client";
import { removeCartItem, setCartQuantity, type CartItem } from "@/lib/cart";
import { availabilityLabel, supplierCountryLabel } from "@/lib/commerce-format";
import { formatPersianNumber, formatTomanFromIrr } from "@/lib/format";
import { useCartSnapshot } from "./use-cart";

export function CartView() {
  const cart = useCartSnapshot();
  const offerQueries = useQueries({
    queries: cart.items.map((item) => ({
      queryKey: ["catalog", "offer", item.offerId],
      queryFn: () => getOfferDetail(item.offerId),
      staleTime: 0,
    })),
  });

  if (!cart.items.length) {
    return (
      <EmptyState
        title="سبد خرید خالی است"
        body="دیدن محصول و ساخت سبد به پروفایل پت نیاز ندارد."
        action={
          <Link className="button button--primary" href="/shop">
            رفتن به فروشگاه
          </Link>
        }
      />
    );
  }

  if (offerQueries.some((query) => query.isLoading)) {
    return (
      <Card className="stack">
        <Skeleton />
        <Skeleton />
        <Skeleton />
      </Card>
    );
  }

  if (offerQueries.some((query) => query.isError)) {
    return (
      <ErrorState
        title="سبد خرید بازخوانی نشد"
        body="قیمت و موجودی فقط از سرویس خوانده می‌شود."
        action={
          <Button
            variant="secondary"
            onClick={() =>
              offerQueries.forEach((query) => void query.refetch())
            }
          >
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  const rows = cart.items.map((item, index) => ({
    item,
    offer: offerQueries[index]?.data ?? null,
  }));
  const unavailableRows = rows.filter(
    (row) => row.offer?.availability !== "available",
  );
  const totalIrr = rows.reduce(
    (sum, row) => sum + (row.offer?.price_irr ?? 0) * row.item.quantity,
    0,
  );

  return (
    <div className="stack">
      <Banner tone={unavailableRows.length ? "warning" : "info"}>
        قیمت، موجودی، ماندگاری و سیاست پرداخت از سرویس دوباره دریافت شد. قیمت در
        سبد محلی ذخیره نمی‌شود.
      </Banner>
      {unavailableRows.length ? (
        <Banner tone="error">
          محصول ناموجود در سبد وجود دارد. قبل از ادامه پرداخت آن را حذف کنید.
        </Banner>
      ) : null}

      <div className="stack">
        {rows.map(({ item, offer }) =>
          offer ? (
            <CartRow key={item.offerId} item={item} offer={offer} />
          ) : null,
        )}
      </div>

      <Card className="split">
        <div>
          <div className="eyebrow">جمع کالا</div>
          <div className="money">{formatTomanFromIrr(totalIrr)}</div>
        </div>
        <Link
          className="button button--primary"
          aria-disabled={unavailableRows.length ? "true" : undefined}
          href={unavailableRows.length ? "/cart" : "/checkout/address"}
        >
          ادامه آدرس
        </Link>
      </Card>
    </div>
  );
}

function CartRow({
  item,
  offer,
}: {
  item: CartItem;
  offer: Awaited<ReturnType<typeof getOfferDetail>>;
}) {
  const unavailable = offer.availability !== "available";
  return (
    <Card className="stack">
      <div className="split">
        <div>
          <div className="eyebrow">
            کشور تامین‌کننده:{" "}
            {supplierCountryLabel(offer.supplier_country_code)}
          </div>
          <h2 className="title">
            <Link href={`/shop/offer/${offer.id}`}>{offer.title_fa}</Link>
          </h2>
        </div>
        <span className={unavailable ? "chip" : "chip chip--active"}>
          {availabilityLabel(offer.availability)}
        </span>
      </div>
      <p className="caption">
        حداقل ماندگاری تحویل:{" "}
        {formatPersianNumber(offer.minimum_shelf_life_months_at_delivery)} ماه
      </p>
      <div className="split">
        <div>
          <div className="eyebrow">قیمت واحد</div>
          <div className="title">{formatTomanFromIrr(offer.price_irr)}</div>
        </div>
        <label className="field cart-quantity">
          <span>تعداد</span>
          <input
            className="input"
            type="number"
            min={1}
            max={100}
            value={item.quantity}
            onChange={(event) =>
              setCartQuantity(item.offerId, Number(event.target.value))
            }
          />
        </label>
      </div>
      <div className="cluster">
        <Button
          variant="secondary"
          onClick={() => removeCartItem(item.offerId)}
        >
          حذف
        </Button>
      </div>
    </Card>
  );
}
