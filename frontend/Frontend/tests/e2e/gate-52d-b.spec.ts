import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
}

test("T10 anonymous browse, cart, commerce address, payment callback and order reload", async ({
  page,
}) => {
  test.setTimeout(45_000);
  await page.goto("/shop");
  await expect(page.getByRole("heading", { name: "کشف محصول" })).toBeVisible();
  await page
    .getByRole("link", { name: /رویال کنین ادالت/ })
    .first()
    .click();

  await expect(page).toHaveURL(/\/shop\/offer\/[0-9a-f-]+$/);
  await expect(
    page.getByText("اصالت: تاییدشده توسط تامین‌کننده"),
  ).toBeVisible();
  await expect(page.getByText("کشور تامین‌کننده")).toBeVisible();
  await expect(page.getByText("فرانسه").first()).toBeVisible();
  await expect(page.getByText(/صرفه‌جویی اعلام‌شده سرویس/)).toBeVisible();
  await expect(page.getByText(/تومان/).first()).toBeVisible();
  await page.getByRole("button", { name: "افزودن به سبد" }).click();

  await page.goto("/cart");
  await expect(page.getByText(/قیمت، موجودی، ماندگاری/)).toBeVisible();
  await page.getByRole("link", { name: "ادامه آدرس" }).click();

  await expect(page.getByText("ورود برای پرداخت لازم است")).toBeVisible();
  await page.getByRole("link", { name: "ورود با موبایل" }).click();
  await page.getByLabel("شماره موبایل").fill("09121234567");
  await page.getByRole("button", { name: "درخواست کد" }).click();
  await page.getByLabel("کد تایید").fill("123456");
  await page.getByRole("button", { name: "تایید و ادامه" }).click();

  await expect(page).toHaveURL(/\/checkout\/address$/);
  await expect(page.getByLabel("نام پت")).toHaveCount(0);
  await page.getByLabel("نام خانوار").fill("خانه خرید");
  await page.getByLabel("نام گیرنده").fill("مالک خانه");
  await page.getByLabel("موبایل گیرنده").fill("09121234567");
  await page.getByLabel("استان").fill("تهران");
  await page.getByLabel("شهر").fill("تهران");
  await page.getByLabel("آدرس کامل").fill("خیابان ولیعصر پلاک ۱۲");
  await page.getByRole("button", { name: "ثبت آدرس و بازبینی سفارش" }).click();

  await expect(page).toHaveURL(/\/checkout\/review$/);
  await expect(page.getByText("۳۶۶ ساعت").first()).toBeVisible();
  await page.getByRole("button", { name: "ساخت سفارش و پرداخت کامل" }).click();

  await expect(page).toHaveURL(/\/checkout\/confirmation\?orderId=/, {
    timeout: 15_000,
  });
  await expect(
    page.getByRole("heading", { name: "تایید سفارش" }),
  ).toBeVisible();
  await expect(
    page.getByText("۳۶۶ ساعت", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/پرداخت تایید شده/)).toBeVisible();
  await expect(
    page.getByText(/تامین کالا فقط پس از پرداخت کامل موفق/),
  ).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("order-detail")).toBeVisible();
  await expectAccessible(page);
});

test("T10 unavailable offers cannot enter checkout", async ({ page }) => {
  await page.goto("/shop/offer/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee");
  await expect(
    page.getByText(
      "این محصول فعلا برای پرداخت کامل در دسترس نیست و وارد فرآیند پرداخت نمی‌شود.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "افزودن به سبد" }),
  ).toBeDisabled();

  await expectAccessible(page);
});

test("T10 callback does not trust browser Status=OK without backend verification", async ({
  page,
}) => {
  await page.goto("/checkout/payment/return?Authority=unknown&Status=OK");
  await expect(page.getByText("پرداخت توسط سرویس تایید نشد")).toBeVisible();
  await expect(page).not.toHaveURL(/\/checkout\/confirmation/);

  await expectAccessible(page);
});
