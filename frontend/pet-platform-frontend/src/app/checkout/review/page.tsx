import { AppShell } from "@/components/app-shell";
import { CheckoutReview } from "@/features/commerce/checkout-review";

export default function CheckoutReviewPage() {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پرداخت</div>
          <h1 className="display">بازبینی سفارش</h1>
        </div>
        <CheckoutReview />
      </div>
    </AppShell>
  );
}
