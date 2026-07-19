import { AppShell } from "@/components/app-shell";
import { OfferCompare } from "@/features/commerce/offer-compare";

export default async function OfferComparePage({
  params,
}: {
  params: Promise<{ offerId: string }>;
}) {
  const { offerId } = await params;

  return (
    <AppShell wide>
      <OfferCompare offerId={offerId} />
    </AppShell>
  );
}
