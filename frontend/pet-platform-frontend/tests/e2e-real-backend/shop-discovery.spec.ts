import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Proves the harness genuinely reaches a live FastAPI + Postgres, not the
// GATE_FIXTURE_MODE in-memory mock every other e2e spec in this repo uses.
// A freshly migrated database has no catalog offers, so this exercises the
// real empty-state response end to end (a real 200 with an empty list, not
// canned fixture data) rather than requiring seed data. Anonymous/no-login
// on purpose: this is the first real-backend slice, kept to the smallest
// reachable surface; authenticated real-backend journeys need a way to
// complete OTP login without live SMS (the backend's dev-console OTP
// fallback logs the code to its own stdout, not any API response) and are
// left for a follow-up iteration.
test("shop discovery renders the real backend's empty catalog, not fixture data", async ({
  page,
}) => {
  await page.goto("/shop");

  await expect(page.getByRole("heading", { name: "کشف محصول" })).toBeVisible();
  await expect(page.getByText("محصولی برای نمایش وجود ندارد")).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
