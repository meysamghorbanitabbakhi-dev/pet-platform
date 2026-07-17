"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
} from "@/components/primitives";
import {
  createAddress,
  createHousehold,
  getMeContext,
  listAddresses,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { writeCheckoutSelection } from "@/lib/checkout-selection";
import { useCartSnapshot } from "./use-cart";

const commerceAddressSchema = z.object({
  addressLine: z.string().min(6, "آدرس کامل لازم است"),
  city: z.string().min(2, "شهر لازم است"),
  householdName: z.string().optional(),
  postalCode: z.string().optional(),
  province: z.string().min(2, "استان لازم است"),
  recipientMobile: z.string().min(10, "موبایل گیرنده لازم است"),
  recipientName: z.string().min(2, "نام گیرنده لازم است"),
});

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس. دوباره تلاش کنید.";
}

export function CheckoutAddress() {
  const cart = useCartSnapshot();
  const router = useRouter();
  const [addingAddress, setAddingAddress] = useState(false);
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
    retry: false,
  });
  const householdId =
    contextQuery.data?.default_household_id ??
    contextQuery.data?.households[0]?.id ??
    null;
  const addressesQuery = useQuery({
    queryKey: ["households", householdId, "addresses"],
    queryFn: () => listAddresses(householdId ?? ""),
    enabled: Boolean(householdId),
  });

  if (!cart.items.length) {
    return (
      <EmptyState
        title="سبد خرید خالی است"
        body="برای ادامه پرداخت ابتدا محصول را به سبد اضافه کنید."
        action={
          <Link className="button button--primary" href="/shop">
            رفتن به فروشگاه
          </Link>
        }
      />
    );
  }

  if (contextQuery.isLoading) {
    return (
      <Card className="stack">
        <Skeleton />
        <Skeleton />
      </Card>
    );
  }

  if (contextQuery.isError) {
    const unauthorized =
      contextQuery.error instanceof ApiError &&
      contextQuery.error.status === 401;
    return (
      <ErrorState
        title={
          unauthorized ? "ورود برای پرداخت لازم است" : "زمینه حساب دریافت نشد"
        }
        body={
          unauthorized
            ? "سبد خرید حفظ می‌شود. پس از تایید کد، همین مسیر ادامه پیدا می‌کند."
            : errorText(contextQuery.error)
        }
        action={
          unauthorized ? (
            <Link
              className="button button--primary"
              href="/auth/mobile?returnTo=/checkout/address"
            >
              ورود با موبایل
            </Link>
          ) : (
            <Button
              variant="secondary"
              onClick={() => void contextQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          )
        }
      />
    );
  }

  if (!householdId) {
    return <AddressForm requireHousehold />;
  }

  if (addressesQuery.isLoading) {
    return (
      <Card className="stack">
        <Skeleton />
        <Skeleton />
      </Card>
    );
  }

  if (addressesQuery.isError) {
    return (
      <ErrorState
        title="آدرس‌ها دریافت نشد"
        body={errorText(addressesQuery.error)}
        action={
          <Button
            variant="secondary"
            onClick={() => void addressesQuery.refetch()}
          >
            تلاش دوباره
          </Button>
        }
      />
    );
  }

  const addresses = addressesQuery.data ?? [];
  return (
    <div className="stack">
      <Banner tone="info">
        پرداخت کامل به هویت، خانوار و آدرس نیاز دارد؛ پروفایل پت برای خرید لازم
        نیست.
      </Banner>
      {addresses.length && !addingAddress ? (
        <>
          {addresses.map((address) => (
            <Card className="stack" key={address.id}>
              <div className="split">
                <div>
                  <div className="eyebrow">{address.label}</div>
                  <h2 className="title">{address.recipient_name}</h2>
                </div>
                <Button
                  variant="selection"
                  onClick={() => {
                    writeCheckoutSelection({
                      addressId: address.id,
                      householdId,
                    });
                    router.push("/checkout/review");
                  }}
                >
                  استفاده از این آدرس
                </Button>
              </div>
              <p className="caption">
                {address.province}، {address.city}، {address.address_line}
              </p>
            </Card>
          ))}
          <Button variant="secondary" onClick={() => setAddingAddress(true)}>
            ثبت آدرس جدید
          </Button>
        </>
      ) : (
        <AddressForm householdId={householdId} />
      )}
    </div>
  );
}

function AddressForm({
  householdId,
  requireHousehold = false,
}: {
  householdId?: string;
  requireHousehold?: boolean;
}) {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof commerceAddressSchema>>({
    resolver: zodResolver(
      requireHousehold
        ? commerceAddressSchema.extend({
            householdName: z.string().min(2, "نام خانوار لازم است"),
          })
        : commerceAddressSchema,
    ),
    defaultValues: {
      addressLine: "",
      city: "",
      householdName: "",
      postalCode: "",
      province: "",
      recipientMobile: "",
      recipientName: "",
    },
  });

  async function onSubmit(values: z.infer<typeof commerceAddressSchema>) {
    setSubmitError(null);
    try {
      const activeHouseholdId =
        householdId ??
        (await createHousehold({ name: values.householdName ?? "" })).id;
      const address = await createAddress(activeHouseholdId, {
        address_line: values.addressLine,
        city: values.city,
        label: "تحویل",
        postal_code: values.postalCode || null,
        province: values.province,
        recipient_mobile: values.recipientMobile,
        recipient_name: values.recipientName,
      });
      writeCheckoutSelection({
        addressId: address.id,
        householdId: activeHouseholdId,
      });
      router.push("/checkout/review");
    } catch (error) {
      setSubmitError(errorText(error));
    }
  }

  return (
    <Card>
      <form className="stack" onSubmit={form.handleSubmit(onSubmit)}>
        {requireHousehold ? (
          <Input
            id="commerce-household"
            label="نام خانوار"
            {...form.register("householdName")}
            error={form.formState.errors.householdName?.message}
          />
        ) : null}
        <Input
          id="checkout-recipient-name"
          label="نام گیرنده"
          {...form.register("recipientName")}
          error={form.formState.errors.recipientName?.message}
        />
        <Input
          id="checkout-recipient-mobile"
          label="موبایل گیرنده"
          inputMode="tel"
          {...form.register("recipientMobile")}
          error={form.formState.errors.recipientMobile?.message}
        />
        <div className="grid grid--two">
          <Input
            id="checkout-province"
            label="استان"
            {...form.register("province")}
            error={form.formState.errors.province?.message}
          />
          <Input
            id="checkout-city"
            label="شهر"
            {...form.register("city")}
            error={form.formState.errors.city?.message}
          />
        </div>
        <Input
          id="checkout-address-line"
          label="آدرس کامل"
          {...form.register("addressLine")}
          error={form.formState.errors.addressLine?.message}
        />
        <Input
          id="checkout-postal-code"
          label="کد پستی"
          inputMode="numeric"
          {...form.register("postalCode")}
        />
        {submitError ? <Banner tone="error">{submitError}</Banner> : null}
        <Button type="submit" loading={form.formState.isSubmitting}>
          ثبت آدرس و بازبینی سفارش
        </Button>
      </form>
    </Card>
  );
}
