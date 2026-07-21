import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { seedOperatorIdentity } from "./seed";
import { waitForOtpCode } from "./otp";

// No journey in design-state-implementation-matrix.md's table covers the
// operator surface at all (all 11 accepted journeys are customer-facing) --
// this is real-backend coverage for a surface that had none, not a
// duplicate of an existing journey. Exercises a second, distinct
// authentication path this repo has never had real-backend coverage for:
// an operator identity (pre-seeded directly, see seed.ts's comment on why
// that is the real code path, not a bypass of it) logging in through the
// same OTP UI a customer uses, then reaching a route gated on
// identity_type='operator' (RLS's app_is_operator(), backend ADR-011's
// amendment) rather than household membership.
test("operator logs in via the real OTP flow and reaches the real KPI dashboard", async ({
  page,
}) => {
  test.setTimeout(30_000);
  const mobileE164 = "+989123456789";
  seedOperatorIdentity(mobileE164);

  const requestedAt = Date.now();
  await page.goto("/auth/mobile");
  await page.getByLabel("شماره موبایل").fill("09123456789");
  await page.getByRole("button", { name: "درخواست کد" }).click();
  await expect(page).toHaveURL(/\/auth\/otp$/);
  const code = await waitForOtpCode(mobileE164, {
    since: requestedAt,
    timeoutMs: 15_000,
  });
  await page.getByLabel("کد تایید").fill(code);
  await page.getByRole("button", { name: "تایید و ادامه" }).click();
  // Wait for the post-verify redirect to actually start (routeFromMeContext
  // has no identity_type branch -- an operator with no households lands on
  // /onboarding/household, which is fine and expected here; this test does
  // not follow it) before navigating away, so the session from verify is
  // guaranteed to be stored first.
  await expect(page).not.toHaveURL(/\/auth\/otp$/, { timeout: 10_000 });

  await page.goto("/operator/kpis");
  await expect(
    page.getByRole("heading", { name: "شاخص‌های عملکرد" }),
  ).toBeVisible();
  // The exact negative this test exists to catch: a customer identity (or
  // a misconfigured RLS/authorization layer) landing here would render
  // the 403 empty state instead.
  await expect(
    page.getByText("این صفحه فقط برای اپراتورها در دسترس است"),
  ).toHaveCount(0);

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
