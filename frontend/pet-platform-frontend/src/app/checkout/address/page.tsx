import { AppShell } from "@/components/app-shell";
import { CheckoutAddress } from "@/features/commerce/checkout-address";

export default function CheckoutAddressPage() {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پرداخت</div>
          <h1 className="display">آدرس تحویل</h1>
        </div>
        <CheckoutAddress />
      </div>
    </AppShell>
  );
}
