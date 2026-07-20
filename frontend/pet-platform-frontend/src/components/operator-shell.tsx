import type { ReactNode } from "react";

// Deliberately not AppShell: AppShell renders the customer-facing
// BottomNav (shop/cart/pets), which has no meaning for an operator and
// would be actively confusing on an operator-only screen.
export function OperatorShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-frame">
      <main className="screen screen--wide">{children}</main>
    </div>
  );
}
