"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Input,
  OtpInput,
} from "@/components/primitives";
import {
  createAddress,
  createHousehold,
  createPet,
  getMeContext,
  requestOtp,
  updatePetProfile,
  verifyOtp,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { consumeReturnTo, storeReturnTo } from "@/lib/auth-return";
import {
  getOnboardingProgress,
  mergeOnboardingProgress,
} from "@/lib/onboarding-progress";

const mobileSchema = z.object({
  mobile: z.string().min(10, "شماره موبایل را کامل وارد کنید"),
});

const householdSchema = z.object({
  name: z.string().min(2, "نام خانوار لازم است"),
});

const petSchema = z.object({
  name: z.string().min(1, "نام پت لازم است"),
  species: z.enum(["dog", "cat"]),
});

const birthDateSchema = z.object({
  birthDate: z.string().optional(),
});

const addressSchema = z.object({
  addressLine: z.string().min(6, "آدرس کامل لازم است"),
  city: z.string().min(2, "شهر لازم است"),
  postalCode: z.string().optional(),
  province: z.string().min(2, "استان لازم است"),
  recipientMobile: z.string().min(10, "موبایل گیرنده لازم است"),
  recipientName: z.string().min(2, "نام گیرنده لازم است"),
});

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس. دوباره تلاش کنید.";
}

function currentReturnTo() {
  if (typeof window === "undefined") return null;
  return new URL(window.location.href).searchParams.get("returnTo");
}

async function resolveHouseholdId() {
  const progress = getOnboardingProgress();
  if (progress.householdId) return progress.householdId;
  const context = await getMeContext();
  const householdId = context.default_household_id ?? context.households[0]?.id;
  if (householdId) mergeOnboardingProgress({ householdId });
  return householdId ?? null;
}

async function resolvePetId() {
  const progress = getOnboardingProgress();
  if (progress.petId) return progress.petId;
  const context = await getMeContext();
  const petId = context.pets[0]?.id;
  if (petId) mergeOnboardingProgress({ petId });
  return petId ?? null;
}

export function AuthMobileForm() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof mobileSchema>>({
    resolver: zodResolver(mobileSchema),
    defaultValues: { mobile: "" },
  });

  async function onSubmit(values: z.infer<typeof mobileSchema>) {
    setSubmitError(null);
    try {
      storeReturnTo(currentReturnTo());
      const response = await requestOtp({
        mobile: values.mobile,
        device_id: "pet-platform-web",
      });
      mergeOnboardingProgress({ challengeId: response.challenge_id });
      router.push("/auth/otp");
    } catch (error) {
      setSubmitError(errorText(error));
    }
  }

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">ورود</div>
          <h1 className="display">شماره موبایل</h1>
        </div>
        <Card>
          <form className="stack" onSubmit={form.handleSubmit(onSubmit)}>
            <Input
              id="mobile"
              label="شماره موبایل"
              inputMode="tel"
              autoComplete="tel"
              {...form.register("mobile")}
              error={form.formState.errors.mobile?.message}
            />
            {submitError ? <Banner tone="error">{submitError}</Banner> : null}
            <Button
              type="submit"
              loading={form.formState.isSubmitting}
              disabled={form.formState.isSubmitting}
            >
              درخواست کد
            </Button>
            <Link className="button button--ghost" href="/shop">
              رفتن به فروشگاه
            </Link>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}

export function AuthOtpForm() {
  const router = useRouter();
  const [challengeId] = useState(
    () => getOnboardingProgress().challengeId ?? null,
  );
  const [otp, setOtp] = useState("");
  const [state, setState] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submitOtp() {
    if (!challengeId || busy) return;
    setBusy(true);
    setSubmitError(null);
    try {
      const response = await verifyOtp({
        challenge_id: challengeId,
        code: otp,
      });
      setState(response.state);
      if (response.state === "verified") {
        router.push(consumeReturnTo() ?? "/onboarding/bootstrap");
      }
    } catch (error) {
      setSubmitError(errorText(error));
    } finally {
      setBusy(false);
    }
  }

  if (challengeId === null) {
    return (
      <AppShell>
        <ErrorState
          title="کد فعال پیدا نشد"
          body="برای ادامه، دوباره کد ورود درخواست کنید."
          action={
            <Link className="button button--primary" href="/auth/mobile">
              درخواست کد تازه
            </Link>
          }
        />
      </AppShell>
    );
  }

  const locked = state === "locked";
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">تایید ورود</div>
          <h1 className="display">کد پیامکی</h1>
        </div>
        <Card className="stack">
          <p className="caption">کد ۶ رقمی پیامک‌شده را وارد کنید.</p>
          <OtpInput
            value={otp}
            onChange={setOtp}
            invalid={state === "invalid"}
          />
          {state === "locked" ? (
            <Banner tone="error">
              تایید کد به دلیل تلاش‌های ناموفق موقتاً قفل شده است.
            </Banner>
          ) : null}
          {["expired", "consumed", "not_found"].includes(state ?? "") ? (
            <Banner tone="warning">
              این کد قابل استفاده نیست. کد تازه درخواست کنید.
            </Banner>
          ) : null}
          {submitError ? <Banner tone="error">{submitError}</Banner> : null}
          <Button
            onClick={submitOtp}
            disabled={otp.length !== 6 || locked || busy}
            loading={busy}
          >
            تایید و ادامه
          </Button>
          <Link className="button button--ghost" href="/auth/mobile">
            درخواست کد تازه
          </Link>
        </Card>
      </div>
    </AppShell>
  );
}

export function HouseholdOnboardingForm() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof householdSchema>>({
    resolver: zodResolver(householdSchema),
    defaultValues: { name: "" },
  });

  async function onSubmit(values: z.infer<typeof householdSchema>) {
    setSubmitError(null);
    try {
      const response = await createHousehold({ name: values.name });
      mergeOnboardingProgress({ householdId: response.id });
      router.push("/onboarding/pet");
    } catch (error) {
      setSubmitError(errorText(error));
    }
  }

  return (
    <OnboardingScreen eyebrow="فعال‌سازی زندگی پت" title="نام خانوار">
      <Card>
        <form className="stack" onSubmit={form.handleSubmit(onSubmit)}>
          <Input
            id="household-name"
            label="نام خانوار"
            autoComplete="organization"
            {...form.register("name")}
            error={form.formState.errors.name?.message}
          />
          {submitError ? <Banner tone="error">{submitError}</Banner> : null}
          <Button type="submit" loading={form.formState.isSubmitting}>
            ثبت خانوار
          </Button>
          <Link className="button button--ghost" href="/shop">
            فروشگاه بدون فعال‌سازی
          </Link>
        </form>
      </Card>
    </OnboardingScreen>
  );
}

export function PetOnboardingForm() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [species, setSpecies] = useState<"dog" | "cat">("dog");
  const form = useForm<z.infer<typeof petSchema>>({
    resolver: zodResolver(petSchema),
    defaultValues: { name: "", species: "dog" },
  });

  async function onSubmit(values: z.infer<typeof petSchema>) {
    setSubmitError(null);
    try {
      const householdId = await resolveHouseholdId();
      if (!householdId) {
        setSubmitError("شناسه خانوار از زمینه حساب دریافت نشد.");
        return;
      }
      const response = await createPet(householdId, {
        name: values.name,
        species: values.species,
      });
      mergeOnboardingProgress({ petId: response.id });
      router.push("/onboarding/pet/birth-date");
    } catch (error) {
      setSubmitError(errorText(error));
    }
  }

  return (
    <OnboardingScreen eyebrow="پروفایل پت" title="نام و گونه پت">
      <Card>
        <form className="stack" onSubmit={form.handleSubmit(onSubmit)}>
          <Input
            id="pet-name"
            label="نام پت"
            {...form.register("name")}
            error={form.formState.errors.name?.message}
          />
          <div className="cluster" role="radiogroup" aria-label="گونه">
            {(["dog", "cat"] as const).map((value) => (
              <Button
                key={value}
                type="button"
                variant={species === value ? "selection" : "secondary"}
                aria-pressed={species === value}
                onClick={() => {
                  setSpecies(value);
                  form.setValue("species", value);
                }}
              >
                {value === "dog" ? "سگ" : "گربه"}
              </Button>
            ))}
          </div>
          {submitError ? <Banner tone="error">{submitError}</Banner> : null}
          <Button type="submit" loading={form.formState.isSubmitting}>
            ثبت پت
          </Button>
        </form>
      </Card>
    </OnboardingScreen>
  );
}

export function PetBirthDateForm() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof birthDateSchema>>({
    resolver: zodResolver(birthDateSchema),
    defaultValues: { birthDate: "" },
  });

  async function submitBirthDate(values: z.infer<typeof birthDateSchema>) {
    setSubmitError(null);
    try {
      const petId = await resolvePetId();
      if (!petId) {
        router.push("/onboarding/address");
        return;
      }
      if (values.birthDate) {
        await updatePetProfile(petId, {
          birth_date: values.birthDate,
          birth_date_precision: "exact",
        });
      }
      router.push("/onboarding/address");
    } catch (error) {
      setSubmitError(errorText(error));
    }
  }

  return (
    <OnboardingScreen eyebrow="پروفایل پت" title="تاریخ تولد">
      <Card>
        <form className="stack" onSubmit={form.handleSubmit(submitBirthDate)}>
          <p className="caption">
            این بخش اختیاری است و می‌توانید بعداً تکمیل کنید.
          </p>
          <Input
            id="birth-date"
            label="تاریخ تولد"
            type="date"
            {...form.register("birthDate")}
          />
          {submitError ? <Banner tone="error">{submitError}</Banner> : null}
          <div className="cluster">
            <Button type="submit" loading={form.formState.isSubmitting}>
              ثبت و ادامه
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => router.push("/onboarding/address")}
            >
              رد کردن
            </Button>
          </div>
        </form>
      </Card>
    </OnboardingScreen>
  );
}

export function AddressOnboardingForm() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof addressSchema>>({
    resolver: zodResolver(addressSchema),
    defaultValues: {
      addressLine: "",
      city: "",
      postalCode: "",
      province: "",
      recipientMobile: "",
      recipientName: "",
    },
  });

  async function onSubmit(values: z.infer<typeof addressSchema>) {
    setSubmitError(null);
    try {
      const householdId = await resolveHouseholdId();
      if (!householdId) {
        setSubmitError("شناسه خانوار از زمینه حساب دریافت نشد.");
        return;
      }
      const response = await createAddress(householdId, {
        address_line: values.addressLine,
        city: values.city,
        label: "خانه",
        postal_code: values.postalCode || null,
        province: values.province,
        recipient_mobile: values.recipientMobile,
        recipient_name: values.recipientName,
      });
      mergeOnboardingProgress({ addressId: response.id });
      router.push("/onboarding/bootstrap");
    } catch (error) {
      setSubmitError(errorText(error));
    }
  }

  return (
    <OnboardingScreen eyebrow="نشانی" title="آدرس تحویل">
      <Card>
        <form className="stack" onSubmit={form.handleSubmit(onSubmit)}>
          <Input
            id="recipient-name"
            label="نام گیرنده"
            {...form.register("recipientName")}
            error={form.formState.errors.recipientName?.message}
          />
          <Input
            id="recipient-mobile"
            label="موبایل گیرنده"
            inputMode="tel"
            {...form.register("recipientMobile")}
            error={form.formState.errors.recipientMobile?.message}
          />
          <div className="grid grid--two">
            <Input
              id="province"
              label="استان"
              {...form.register("province")}
              error={form.formState.errors.province?.message}
            />
            <Input
              id="city"
              label="شهر"
              {...form.register("city")}
              error={form.formState.errors.city?.message}
            />
          </div>
          <Input
            id="address-line"
            label="آدرس کامل"
            {...form.register("addressLine")}
            error={form.formState.errors.addressLine?.message}
          />
          <Input
            id="postal-code"
            label="کد پستی"
            inputMode="numeric"
            {...form.register("postalCode")}
          />
          {submitError ? <Banner tone="error">{submitError}</Banner> : null}
          <Button type="submit" loading={form.formState.isSubmitting}>
            ثبت آدرس و رفتن به امروز
          </Button>
        </form>
      </Card>
    </OnboardingScreen>
  );
}

function OnboardingScreen({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h1 className="display">{title}</h1>
        </div>
        {children}
      </div>
    </AppShell>
  );
}
