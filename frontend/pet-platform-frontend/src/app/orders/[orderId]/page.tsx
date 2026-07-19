import { AppShell } from "@/components/app-shell";
import { OrderDetailView } from "@/features/commerce/order-detail-view";

export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const { orderId } = await params;
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">سفارش</div>
          <h1 className="display">جزئیات سفارش</h1>
        </div>
        <OrderDetailView orderId={orderId} />
      </div>
    </AppShell>
  );
}
