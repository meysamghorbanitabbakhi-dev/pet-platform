import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
}

async function setCompleteFixtureContext(page: Page) {
  await page.context().addCookies([
    {
      name: "pet_dev_onboarding",
      value: "complete",
      domain: "127.0.0.1",
      path: "/",
    },
    {
      name: "pet_csrf",
      value: "fixture-csrf",
      domain: "127.0.0.1",
      path: "/",
    },
  ]);
}

async function setUnopenedTodayFixture(page: Page) {
  await page.context().addCookies([
    {
      name: "pet_dev_today_state",
      value: "unopened",
      domain: "127.0.0.1",
      path: "/",
    },
  ]);
}

test("T9 Today is RTL, reload-safe, understandable without a tap, and accessible", async ({
  page,
}) => {
  await setCompleteFixtureContext(page);
  await page.goto("/onboarding/bootstrap");
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();
  await expect(page.getByText("وضعیت اصلی امروز")).toBeVisible();
  await expect(page.getByText("رویداد بعدی")).toBeVisible();
  await expect(page.getByTestId("garden-preview")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("today-dashboard")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(
    /XP|امتیاز|سلامت|خرید|استریک|افت/,
  );

  await expectAccessible(page);
});

test("T8 first owner completes canonical onboarding and ends at Today", async ({
  page,
}) => {
  await page.goto("/auth/mobile");
  await page.getByLabel("شماره موبایل").fill("09121234567");
  await page.getByRole("button", { name: "درخواست کد" }).click();
  await expect(page).toHaveURL(/\/auth\/otp$/);

  await page.getByLabel("کد تایید").fill("123456");
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
  await page.getByRole("button", { name: "ثبت آدرس و رفتن به Today" }).click();
  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByTestId("today-dashboard")).toBeVisible();

  await expectAccessible(page);
});

test("OTP error and locked states are explicit and duplicate-safe", async ({
  page,
}) => {
  await page.goto("/auth/mobile");
  await page.getByLabel("شماره موبایل").fill("09121234567");
  await page.getByRole("button", { name: "درخواست کد" }).click();
  await page.getByLabel("کد تایید").fill("000000");
  await page.getByRole("button", { name: "تایید و ادامه" }).click();
  await expect(page.getByText("کد وارد شده معتبر نیست")).toBeVisible();

  await page.getByLabel("کد تایید").fill("999999");
  await page.getByRole("button", { name: "تایید و ادامه" }).click();
  await expect(page.getByText(/قفل شده است/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "تایید و ادامه" }),
  ).toBeDisabled();
});

test("Shop discovery is server-rendered and labels toman from runtime policy", async ({
  page,
}) => {
  await page.goto("/shop");
  await expect(page.getByRole("heading", { name: "کشف محصول" })).toBeVisible();
  await expect(page.getByText("تومان").first()).toBeVisible();
  await expect(page.getByText(/اصالت/).first()).toBeVisible();

  await expectAccessible(page);
});

test("Inventory opening uses the real unit route id and does not invent an estimate", async ({
  page,
}) => {
  await setCompleteFixtureContext(page);
  await setUnopenedTodayFixture(page);
  await page.goto("/today");
  const openLink = page.getByRole("link", { name: "تایید باز شدن بسته" });
  await expect(openLink).toHaveAttribute("href", /\/inventory\/[0-9a-f-]+/);
  await openLink.click();
  await expect(page).toHaveURL(/\/inventory\/[0-9a-f-]+$/);
  await expect(
    page.getByText("تخمین روز باقی‌مانده شروع نمی‌شود"),
  ).toBeVisible();
  await page.getByRole("button", { name: "تایید باز شدن بسته" }).click();
  await expect(page.getByText(/باز شدن بسته ثبت شد/)).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/۱۲ تا ۱۸ روز/);

  await expectAccessible(page);
});
