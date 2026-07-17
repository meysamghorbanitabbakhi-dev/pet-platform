import { AppShell } from "@/components/app-shell";
import { ErrorState } from "@/components/primitives";
import { OfferDetail } from "@/features/commerce/offer-detail";
import { getOfferDetailServer, getPoliciesServer } from "@/lib/api/server";

export const dynamic = "force-dynamic";

export default async function OfferDetailPage({
  params,
}: {
  params: Promise<{ offerId: string }>;
}) {
  const { offerId } = await params;
  const result = await loadOffer(offerId);
  if (!result.ok) {
    return (
      <AppShell>
        <ErrorState
          title="جزئیات محصول دریافت نشد"
          body="این صفحه فقط از داده سرویس استفاده می‌کند. اتصال سرویس یا شناسه محصول را بررسی کنید."
        />
      </AppShell>
    );
  }

  return (
    <AppShell wide>
      <OfferDetail offer={result.offer} policy={result.policy} />
    </AppShell>
  );
}

async function loadOffer(offerId: string) {
  try {
    const [offer, policy] = await Promise.all([
      getOfferDetailServer(offerId),
      getPoliciesServer(),
    ]);
    return { ok: true as const, offer, policy };
  } catch {
    return { ok: false as const };
  }
}
