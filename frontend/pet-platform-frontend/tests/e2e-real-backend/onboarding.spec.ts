import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { waitForOtpCode } from "./otp";

// T8 (see design-state-implementation-matrix.md's journey table) against a
// genuinely live backend + Postgres, not GATE_FIXTURE_MODE's mock -- the OTP
// step is the reason no prior real-backend spec covered an authenticated
// journey: the code only ever reaches the backend's own stderr (dev-console
// fallback), never an API response, so it has to be read from there.
test("T8 first owner completes canonical onboarding against the real backend and ends at Today", async ({
  page,
}) => {
  test.setTimeout(45_000);
  const mobile = "+989121234567";
  const requestedAt = Date.now();

  await page.goto("/auth/mobile");
  await page.getByLabel("شماره موبایل").fill("09121234567");
  await page.getByRole("button", { name: "درخواست کد" }).click();
  await expect(page).toHaveURL(/\/auth\/otp$/);

  const code = await waitForOtpCode(mobile, {
    since: requestedAt,
    timeoutMs: 15_000,
  });

  await page.getByLabel("کد تایید").fill(code);
  await page.getByRole("button", { name: "تایید و ادامه" }).click();
  await expect(page).toHaveURL(/\/onboarding\/household$/);

  await page.getByLabel("نام خانوار").fill("خانه بیشی");
  await page.getByRole("button", { name: "ثبت خانوار" }).click();
  await expect(page).toHaveURL(/\/onboarding\/pet$/);

  await page.getByLabel("نام پت").fill("بیشی");
  await page.getByRole("button", { name: "ثبت پت" }).click();
  await expect(page).toHaveURL(/\/onboarding\/pet\/birth-date$/);

  await page.getByRole("button", { name: "رد کردن" }).click();
  await expect(page).toHaveURL(/\/onboarding\/address$/);

  await page.getByLabel("نام گیرنده").fill("مالک خانه");
  await page.getByLabel("موبایل گیرنده").fill("09121234567");
  await page.getByLabel("استان").fill("تهران");
  await page.getByLabel("شهر").fill("تهران");
  await page.getByLabel("آدرس کامل").fill("خیابان ولیعصر پلاک ۱۲");
  await page.getByRole("button", { name: "ثبت آدرس و رفتن به امروز" }).click();
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByTestId("today-dashboard")).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
