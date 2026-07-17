"use client";

import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Banner, Button, Card } from "@/components/primitives";
import { openInventory } from "@/lib/api/client";
import { ids, inventoryDetailFixture } from "@/lib/fixtures/gate-fixtures";

export function InventoryOpening() {
  const [state, setState] = useState<"ready" | "opened">("ready");
  const [busy, setBusy] = useState(false);

  async function confirmOpening() {
    setBusy(true);
    try {
      await openInventory(ids.inventoryUnit, {
        feeding_context: "unknown",
        remaining: null,
        remaining_grams: null,
      });
      setState("opened");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">انبار خانوار</div>
          <h1 className="display">باز کردن بسته</h1>
        </div>
        <Card className="stack">
          <h2 className="title">{inventoryDetailFixture.label}</h2>
          <p className="caption">
            این واحد فیزیکی متعلق به خانوار است. نسبت مصرف پت بعد از setup از آن
            جدا ثبت می‌شود.
          </p>
          {state === "ready" ? (
            <>
              <Banner tone="warning">
                تا قبل از تأیید باز شدن بسته، تخمین روز باقی‌مانده شروع نمی‌شود.
              </Banner>
              <Button onClick={confirmOpening} loading={busy}>
                تأیید باز شدن بسته
              </Button>
            </>
          ) : (
            <Banner tone="info">
              باز شدن بسته ثبت شد. برای تخمین دقیق‌تر، backend داده کافی مصرف را
              تعیین می‌کند.
            </Banner>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
