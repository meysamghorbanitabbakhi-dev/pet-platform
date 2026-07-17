import { AppShell } from "@/components/app-shell";
import { CartView } from "@/features/commerce/cart-view";

export default function CartPage() {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">سبد خرید</div>
          <h1 className="display">سبد</h1>
        </div>
        <CartView />
      </div>
    </AppShell>
  );
}
