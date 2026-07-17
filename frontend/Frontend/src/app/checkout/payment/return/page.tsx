import { AppShell } from "@/components/app-shell";
import { PaymentReturn } from "@/features/commerce/payment-return";

export default async function CheckoutPaymentReturnPage({
  searchParams,
}: {
  searchParams: Promise<{ Authority?: string; Status?: string }>;
}) {
  const { Authority, Status } = await searchParams;
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پرداخت</div>
          <h1 className="display">بازگشت از درگاه</h1>
        </div>
        <PaymentReturn authority={Authority} status={Status} />
      </div>
    </AppShell>
  );
}
