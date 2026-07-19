"use client";

import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { Button, ErrorState } from "@/components/primitives";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.error(error);
    }
  }, [error]);

  return (
    <AppShell>
      <ErrorState
        title="خطای غیرمنتظره رخ داد"
        body="این صفحه با خطا مواجه شد. می‌توانید دوباره تلاش کنید."
        action={
          <Button variant="secondary" onClick={reset}>
            تلاش دوباره
          </Button>
        }
      />
    </AppShell>
  );
}
