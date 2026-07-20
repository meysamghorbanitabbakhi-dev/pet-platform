import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { retireOffer, seedFullPaymentOffer } from "./seed";
import { waitForOtpCode } from "./otp";

// T10 (see design-state-implementation-matrix.md's journey table) against a
// genuinely live backend + Postgres: شاپ -> جزئیات -> سبد -> آدرس -> بازبینی
// -> ساخت سفارش. Stops at the payment-redirect step's honest
// provider-not-configured state rather than a completed payment --
// ZARINPAL_MERCHANT_ID is empty in this harness (see
// scripts/e2e-real-backend.mjs and backend ADR "external integrations"
// notes), so there is no real sandbox credential to redirect to. This is
// not a workaround: PaymentRedirect's own 503 branch is the real,
// shipped behavior for exactly this configuration state, not a mock --
// asserting it is asserting a real code path, not skipping one.
test("T10 shop discovery through order creation reaches the real payment gateway boundary", async ({
  page,
}) => {
  test.setTimeout(45_000);
  const offer = seedFullPaymentOffer();

  try {
    const mobile = "+989122345678";
    const requestedAt = Date.now();
    await page.goto("/auth/mobile");
    await page.getByLabel("شماره موبایل").fill("09122345678");
    await page.getByRole("button", { name: "درخواست کد" }).click();
    await expect(page).toHaveURL(/\/auth\/otp$/);
    const code = await waitForOtpCode(mobile, { since: requestedAt, timeoutMs: 15_000 });
    await page.getByLabel("کد تایید").fill(code);
    await page.getByRole("button", { name: "تایید و ادامه" }).click();
    await expect(page).toHaveURL(/\/onboarding\/household$/);

    await page.getByLabel("نام خانوار").fill("خانه تست پرداخت");
    await page.getByRole("button", { name: "ثبت خانوار" }).click();
    await expect(page).toHaveURL(/\/onboarding\/pet$/);
    await page.getByLabel("نام پت").fill("مولی");
    await page.getByRole("button", { name: "ثبت پت" }).click();
    await expect(page).toHaveURL(/\/onboarding\/pet\/birth-date$/);
    await page.getByRole("button", { name: "رد کردن" }).click();
    await expect(page).toHaveURL(/\/onboarding\/address$/);
    await page.getByLabel("نام گیرنده").fill("مالک خانه");
    await page.getByLabel("موبایل گیرنده").fill("09122345678");
    await page.getByLabel("استان").fill("تهران");
    await page.getByLabel("شهر").fill("تهران");
    await page.getByLabel("آدرس کامل").fill("خیابان ولیعصر پلاک ۱۲");
    await page.getByRole("button", { name: "ثبت آدرس و رفتن به امروز" }).click();
    await expect(page).toHaveURL(/\/today$/);

    await page.goto("/shop");
    await expect(page.getByRole("heading", { name: "کشف محصول" })).toBeVisible();
    await page.getByRole("link", { name: offer.title, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/shop/offer/${offer.offerId}$`));
    await expect(page.getByRole("heading", { name: offer.title })).toBeVisible();

    const addToCartResults = await new AxeBuilder({ page }).analyze();
    expect(addToCartResults.violations).toEqual([]);

    await page.getByRole("button", { name: "افزودن به سبد" }).click();
    await expect(page.getByRole("button", { name: "به سبد افزوده شد" })).toBeVisible();
    await page.getByRole("link", { name: "مشاهده سبد" }).click();
    await expect(page).toHaveURL(/\/cart$/);
    await expect(page.getByText(offer.title)).toBeVisible();

    await page.getByRole("link", { name: "ادامه آدرس" }).click();
    await expect(page).toHaveURL(/\/checkout\/address$/);
    await page.getByRole("button", { name: "استفاده از این آدرس" }).click();
    await expect(page).toHaveURL(/\/checkout\/review$/);

    await page.getByRole("button", { name: "ساخت سفارش و پرداخت کامل" }).click();
    await expect(page).toHaveURL(/\/checkout\/payment\/redirect/);
    await expect(page.getByText("درگاه پرداخت پیکربندی نشده است")).toBeVisible({
      timeout: 10_000,
    });

    const finalResults = await new AxeBuilder({ page }).analyze();
    expect(finalResults.violations).toEqual([]);

    // The order itself was genuinely created (the payment gateway is
    // what's unconfigured, not checkout) -- confirm it shows up in real
    // order history, proving the whole chain committed for real. Order
    // history rows show date/status/total, not the product title
    // (order-history.tsx), so this asserts the empty-state is gone and a
    // real row is present, not text that was never going to be there.
    await page.goto("/orders");
    await expect(page.getByText("هنوز سفارشی ثبت نشده است")).toHaveCount(0);
    await expect(page.getByLabel("فهرست سفارش‌ها").getByRole("listitem")).toHaveCount(1);
  } finally {
    // This harness's ephemeral Postgres has no per-spec-file reset (see
    // seed.ts) -- retire even on failure, or a thrown assertion above
    // would leave a live offer for shop-discovery.spec.ts (or any future
    // spec asserting an empty/known catalog) to trip over.
    retireOffer(offer.offerId);
  }
});
