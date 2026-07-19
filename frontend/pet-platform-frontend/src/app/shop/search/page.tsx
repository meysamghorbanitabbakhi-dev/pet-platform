import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
import { Card, Skeleton } from "@/components/primitives";
import { OfferSearch } from "@/features/commerce/offer-search";

function SearchFallback() {
  return (
    <AppShell wide>
      <div className="stack">
        <div>
          <div className="eyebrow">فروشگاه</div>
          <h1 className="display">جستجوی محصول</h1>
        </div>
        <Card className="stack">
          <Skeleton />
        </Card>
      </div>
    </AppShell>
  );
}

export default function ShopSearchPage() {
  return (
    <Suspense fallback={<SearchFallback />}>
      <OfferSearch />
    </Suspense>
  );
}
