import { AppShell } from "@/components/app-shell";
import { PaymentRedirect } from "@/features/commerce/payment-redirect";

export default async function CheckoutPaymentRedirectPage({
  searchParams,
}: {
  searchParams: Promise<{ orderId?: string }>;
}) {
  const { orderId } = await searchParams;
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پرداخت</div>
          <h1 className="display">انتقال به درگاه</h1>
        </div>
        <PaymentRedirect orderId={orderId} />
      </div>
    </AppShell>
  );
}
