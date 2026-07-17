import { AppShell } from "@/components/app-shell";
import { OrderDetailView } from "@/features/commerce/order-detail-view";

export default async function CheckoutConfirmationPage({
  searchParams,
}: {
  searchParams: Promise<{ orderId?: string }>;
}) {
  const { orderId } = await searchParams;
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">سفارش تاییدشده</div>
          <h1 className="display">تایید سفارش</h1>
        </div>
        <OrderDetailView confirmation orderId={orderId} />
      </div>
    </AppShell>
  );
}
