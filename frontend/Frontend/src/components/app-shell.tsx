import type { ReactNode } from "react";
import { BottomNav } from "@/components/primitives";

export function AppShell({
  children,
  wide = false,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="app-frame">
      <main className={wide ? "screen screen--wide" : "screen"}>
        {children}
      </main>
      <BottomNav />
    </div>
  );
}
