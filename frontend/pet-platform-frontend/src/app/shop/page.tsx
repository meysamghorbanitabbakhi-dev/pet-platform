import { AppShell } from "@/components/app-shell";
import { ErrorState } from "@/components/primitives";
import { OfferList } from "@/features/commerce/offer-list";
import { getPoliciesServer, listOffersServer } from "@/lib/api/server";

export const dynamic = "force-dynamic";

export default async function ShopPage() {
  const result = await loadOffers();
  if (!result.ok) {
    return (
      <AppShell>
        <ErrorState
          title="فروشگاه در دسترس نیست"
          body="لیست محصول فقط از backend خوانده می‌شود. اتصال سرویس را بررسی کنید."
        />
      </AppShell>
    );
  }

  return (
    <AppShell wide>
      <div className="stack">
        <div>
          <div className="eyebrow">فروشگاه</div>
          <h1 className="display">کشف محصول</h1>
        </div>
        <p className="caption">
          این صفحه با Server Component داده محصول را از backend می‌خواند. قیمت
          در backend به ریال ذخیره شده و اینجا با برچسب تومان نمایش داده می‌شود.
        </p>
        <OfferList offers={result.offers} policy={result.policy} />
      </div>
    </AppShell>
  );
}

async function loadOffers() {
  try {
    const [offers, policy] = await Promise.all([
      listOffersServer(),
      getPoliciesServer(),
    ]);
    return { ok: true as const, offers, policy };
  } catch {
    return { ok: false as const };
  }
}
