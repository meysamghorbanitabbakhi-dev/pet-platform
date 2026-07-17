"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AppShell } from "@/components/app-shell";
import { Banner, Button, Card, Input, OtpInput } from "@/components/primitives";
import type {
  OtpRequestBody,
  OtpRequestResponse,
  OtpVerifyBody,
  OtpVerifyResponse,
} from "@/lib/api-types";
import {
  createAddress,
  createHousehold,
  createPet,
  openInventory,
  requestOtp,
  verifyOtp,
} from "@/lib/api/client";
import { ids } from "@/lib/fixtures/gate-fixtures";

type Step =
  | "mobile"
  | "otp"
  | "onboarding"
  | "commerce"
  | "incoming"
  | "receipt"
  | "opened"
  | "today";
type FlowApi = {
  requestOtp: (body: OtpRequestBody) => Promise<OtpRequestResponse>;
  verifyOtp: (body: OtpVerifyBody) => Promise<OtpVerifyResponse>;
  createHousehold?: typeof createHousehold;
  createPet?: typeof createPet;
  createAddress?: typeof createAddress;
};

const mobileSchema = z.object({
  mobile: z.string().min(10, "شماره موبایل را کامل وارد کنید"),
});

const onboardingSchema = z.object({
  addressLine: z.string().min(6, "آدرس کامل لازم است"),
  city: z.string().min(2, "شهر لازم است"),
  householdName: z.string().min(2, "نام خانوار لازم است"),
  petName: z.string().optional(),
  province: z.string().min(2, "استان لازم است"),
  recipientMobile: z.string().min(10, "موبایل گیرنده لازم است"),
  recipientName: z.string().min(2, "نام گیرنده لازم است"),
  species: z.enum(["dog", "cat"]),
});

const defaultFlowApi: Required<FlowApi> = {
  createAddress,
  createHousehold,
  createPet,
  requestOtp,
  verifyOtp,
};

export function FirstOwnerFlow({ api = defaultFlowApi }: { api?: FlowApi }) {
  const [step, setStep] = useState<Step>("mobile");
  const [challenge, setChallenge] = useState<OtpRequestResponse | null>(null);
  const [otp, setOtp] = useState("");
  const [otpState, setOtpState] = useState<OtpVerifyResponse["state"] | null>(
    null,
  );
  const [selectedSpecies, setSelectedSpecies] = useState<"dog" | "cat">("dog");
  const [busy, setBusy] = useState(false);

  const mobileForm = useForm<z.infer<typeof mobileSchema>>({
    resolver: zodResolver(mobileSchema),
    defaultValues: { mobile: "09121234567" },
  });
  const onboardingForm = useForm<z.infer<typeof onboardingSchema>>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      addressLine: "خیابان ولیعصر، پلاک ۱۲",
      city: "تهران",
      householdName: "خانه بیشی",
      petName: "بیشی",
      province: "تهران",
      recipientMobile: "09121234567",
      recipientName: "مالک خانه",
      species: "dog",
    },
  });

  async function submitMobile(values: z.infer<typeof mobileSchema>) {
    setBusy(true);
    try {
      const response = await api.requestOtp({
        mobile: values.mobile,
        device_id: "web",
      });
      setChallenge(response);
      setStep("otp");
    } finally {
      setBusy(false);
    }
  }

  async function submitOtp() {
    if (!challenge) return;
    setBusy(true);
    try {
      const response = await api.verifyOtp({
        challenge_id: challenge.challenge_id,
        code: otp,
      });
      setOtpState(response.state);
      if (response.state === "verified") setStep("onboarding");
    } finally {
      setBusy(false);
    }
  }

  async function confirmOpening() {
    setBusy(true);
    try {
      await openInventory(ids.inventoryUnit, {
        feeding_context: "unknown",
        remaining: null,
        remaining_grams: null,
      });
      setStep("opened");
    } finally {
      setBusy(false);
    }
  }

  async function submitOnboarding(values: z.infer<typeof onboardingSchema>) {
    setBusy(true);
    try {
      const household = await (api.createHousehold ?? createHousehold)({
        name: values.householdName,
      });
      if (values.petName) {
        await (api.createPet ?? createPet)(household.id, {
          name: values.petName,
          species: values.species,
        });
      }
      await (api.createAddress ?? createAddress)(household.id, {
        address_line: values.addressLine,
        city: values.city,
        label: "خانه",
        postal_code: null,
        province: values.province,
        recipient_mobile: values.recipientMobile,
        recipient_name: values.recipientName,
      });
      setStep("incoming");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="stack" data-testid="first-owner-flow">
        <div>
          <div className="eyebrow">T8 نخستین مالک</div>
          <h1 className="display">شروع استفاده</h1>
        </div>

        {step === "mobile" ? (
          <Card>
            <form
              className="stack"
              onSubmit={mobileForm.handleSubmit(submitMobile)}
            >
              <h2 className="title">ورود با شماره موبایل</h2>
              <Input
                id="mobile"
                label="شماره موبایل"
                inputMode="tel"
                {...mobileForm.register("mobile")}
                error={mobileForm.formState.errors.mobile?.message}
              />
              <Button type="submit" loading={busy}>
                درخواست کد
              </Button>
            </form>
          </Card>
        ) : null}

        {step === "otp" ? (
          <Card className="stack">
            <h2 className="title">تأیید شماره موبایل</h2>
            <p className="caption">کد ۶ رقمی پیامک‌شده را وارد کنید.</p>
            <OtpInput
              value={otp}
              onChange={setOtp}
              invalid={otpState === "invalid"}
            />
            {otpState === "locked" ? (
              <Banner tone="error">
                به دلیل تلاش‌های ناموفق مکرر، تأیید کد موقتاً قفل شده است.
              </Banner>
            ) : null}
            {otpState === "expired" ||
            otpState === "consumed" ||
            otpState === "not_found" ? (
              <Banner tone="warning">
                کد فعلی قابل استفاده نیست. کد تازه درخواست کنید.
              </Banner>
            ) : null}
            <Button
              onClick={submitOtp}
              disabled={otp.length !== 6 || otpState === "locked"}
              loading={busy}
            >
              تأیید و ادامه
            </Button>
          </Card>
        ) : null}

        {step === "onboarding" ? (
          <Card>
            <form
              className="stack"
              onSubmit={onboardingForm.handleSubmit(submitOnboarding)}
            >
              <h2 className="title">پروفایل پت اختیاری است</h2>
              <p className="caption">
                می‌توانید پت را ثبت کنید یا فعلاً وارد فروشگاه شوید. تجارت بدون
                پروفایل پت قابل استفاده می‌ماند.
              </p>
              <Input
                id="householdName"
                label="نام خانوار"
                {...onboardingForm.register("householdName")}
                error={onboardingForm.formState.errors.householdName?.message}
              />
              <Input
                id="petName"
                label="نام پت (اختیاری)"
                {...onboardingForm.register("petName")}
              />
              <Input
                id="recipientName"
                label="نام گیرنده"
                {...onboardingForm.register("recipientName")}
                error={onboardingForm.formState.errors.recipientName?.message}
              />
              <Input
                id="recipientMobile"
                label="موبایل گیرنده"
                inputMode="tel"
                {...onboardingForm.register("recipientMobile")}
                error={onboardingForm.formState.errors.recipientMobile?.message}
              />
              <div className="grid grid--two">
                <Input
                  id="province"
                  label="استان"
                  {...onboardingForm.register("province")}
                  error={onboardingForm.formState.errors.province?.message}
                />
                <Input
                  id="city"
                  label="شهر"
                  {...onboardingForm.register("city")}
                  error={onboardingForm.formState.errors.city?.message}
                />
              </div>
              <Input
                id="addressLine"
                label="آدرس کامل"
                {...onboardingForm.register("addressLine")}
                error={onboardingForm.formState.errors.addressLine?.message}
              />
              <div className="cluster" role="radiogroup" aria-label="گونه">
                <Button
                  type="button"
                  variant={
                    selectedSpecies === "dog" ? "selection" : "secondary"
                  }
                  onClick={() => {
                    setSelectedSpecies("dog");
                    onboardingForm.setValue("species", "dog");
                  }}
                >
                  سگ
                </Button>
                <Button
                  type="button"
                  variant={
                    selectedSpecies === "cat" ? "selection" : "secondary"
                  }
                  onClick={() => {
                    setSelectedSpecies("cat");
                    onboardingForm.setValue("species", "cat");
                  }}
                >
                  گربه
                </Button>
              </div>
              <div className="cluster">
                <Button type="submit" loading={busy}>
                  ادامه با پروفایل
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setStep("commerce")}
                >
                  رد کردن و رفتن به فروشگاه
                </Button>
              </div>
            </form>
          </Card>
        ) : null}

        {step === "commerce" ? (
          <Card className="stack">
            <h2 className="title">فروشگاه در دسترس است</h2>
            <p className="caption">
              رد کردن پروفایل پت خرید را متوقف نمی‌کند. پرداخت باید کامل باشد و
              رزرو اکنون فعال نیست.
            </p>
            <Link className="button button--selection" href="/shop">
              مشاهده فروشگاه
            </Link>
            <Button onClick={() => setStep("incoming")}>
              نمایش وضعیت سفارش پرداخت‌شده
            </Button>
          </Card>
        ) : null}

        {step === "incoming" ? (
          <Card className="stack">
            <span className="chip chip--active">پرداخت کامل ثبت شد</span>
            <h2 className="title">سفارش وارد مرحله تأمین شده است</h2>
            <p>
              تأمین فقط پس از پرداخت کامل شروع شده است. تعهد تحویل دقیقاً ۳۶۶
              ساعت است.
            </p>
            <Button onClick={() => setStep("receipt")}>
              ثبت رسید تحویل و انبار
            </Button>
          </Card>
        ) : null}

        {step === "receipt" ? (
          <Card className="stack">
            <h2 className="title">رسید انبار خانوار</h2>
            <p>
              بسته به انبار خانوار اضافه شد. تا تأیید باز شدن بسته، تخمین مصرف
              پت شروع نمی‌شود.
            </p>
            <Button onClick={confirmOpening} loading={busy}>
              تأیید باز شدن بسته
            </Button>
          </Card>
        ) : null}

        {step === "opened" ? (
          <Card className="stack">
            <h2 className="title">setup بسته ثبت شد</h2>
            <p>
              امروز فعال است، اما تا دریافت داده کافی فقط وضعیت setup نمایش داده
              می‌شود.
            </p>
            <Button onClick={() => setStep("today")}>رفتن به امروز</Button>
          </Card>
        ) : null}

        {step === "today" ? (
          <Card className="stack">
            <h2 className="title">امروز بدون تخمین زودهنگام</h2>
            <p>
              وضعیت فعلی: بسته باز شده و setup ثبت شده است؛ عدد روز باقی‌مانده
              هنوز نمایش داده نمی‌شود.
            </p>
            <Link className="button button--primary" href="/today">
              مشاهده Today
            </Link>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}
