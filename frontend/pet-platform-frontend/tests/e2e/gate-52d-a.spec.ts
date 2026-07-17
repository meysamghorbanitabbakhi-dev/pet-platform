import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("Today is RTL, understandable without a tap, responsive, and accessible", async ({
  page,
}) => {
  await page.goto("/today");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { name: "امروز" })).toBeVisible();
  await expect(page.getByText("وضعیت اصلی امروز")).toBeVisible();
  await expect(page.getByText("رویداد بعدی")).toBeVisible();
  await expect(page.getByTestId("garden-preview")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(
    /XP|امتیاز|سلامت|خرید|استریک|افت/,
  );

  const results = await new AxeBuilder({ page })
    .disableRules(["color-contrast"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("T8 first owner can skip pet onboarding and keep commerce usable", async ({
  page,
}) => {
  await page.goto("/auth/mobile");
  await page.getByRole("button", { name: "درخواست کد" }).click();
  await page.getByLabel("کد تایید").fill("123456");
  await page.getByRole("button", { name: "تأیید و ادامه" }).click();
  await expect(page.getByText("پروفایل پت اختیاری است")).toBeVisible();
  await page.getByRole("button", { name: "رد کردن و رفتن به فروشگاه" }).click();
  await expect(
    page.getByRole("link", { name: "مشاهده فروشگاه" }),
  ).toHaveAttribute("href", "/shop");
});

test("Shop discovery is server-rendered and labels toman", async ({ page }) => {
  await page.goto("/shop");
  await expect(page.getByRole("heading", { name: "کشف محصول" })).toBeVisible();
  await expect(page.getByText("تومان").first()).toBeVisible();
  await expect(page.getByText("اصالت تأییدشده").first()).toBeVisible();
});
