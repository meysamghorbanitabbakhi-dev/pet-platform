"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Money,
  Sheet,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import {
  getMeContext,
  getWallet,
  listAddresses,
  listHouseholdPets,
  logout,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";

const speciesLabelFa: Record<string, string> = {
  cat: "گربه",
  dog: "سگ",
};

export function AccountOverview() {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const [showLogoutSheet, setShowLogoutSheet] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
  });

  const householdId =
    contextQuery.data?.default_household_id ??
    contextQuery.data?.households[0]?.id ??
    null;

  const petsQuery = useQuery({
    queryKey: ["households", householdId, "pets"],
    queryFn: () => listHouseholdPets(householdId as string),
    enabled: Boolean(householdId),
  });

  const addressesQuery = useQuery({
    queryKey: ["households", householdId, "addresses"],
    queryFn: () => listAddresses(householdId as string),
    enabled: Boolean(householdId),
  });

  const walletQuery = useQuery({
    queryKey: ["households", householdId, "wallet"],
    queryFn: () => getWallet(householdId as string),
    enabled: Boolean(householdId),
  });

  const sessionExpired =
    contextQuery.error instanceof ApiError && contextQuery.error.status === 401;

  useEffect(() => {
    if (sessionExpired) router.replace("/auth/session-expired");
  }, [sessionExpired, router]);

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

  if (contextQuery.isError) {
    return (
      <AppShell>
        <ErrorState
          title="خطا در دریافت حساب"
          body="اتصال را بررسی کنید و دوباره تلاش کنید."
          action={
            <Button variant="secondary" onClick={() => void contextQuery.refetch()}>
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  if (!contextQuery.data) {
    return (
      <AppShell>
        <div className="stack">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      </AppShell>
    );
  }

  const { identity, households } = contextQuery.data;
  const household = households.find((item) => item.id === householdId) ?? null;

  async function confirmLogout() {
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
      router.replace("/auth/mobile");
    } catch (error) {
      setLogoutError(
        error instanceof ApiError ? error.message : "خروج از حساب ناموفق بود.",
      );
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">حساب</div>
          <h1 className="display">حساب کاربری</h1>
        </div>

        <Card className="stack">
          <div className="split">
            <div>
              <div className="eyebrow">شماره موبایل</div>
              <div className="title ltr-data">{identity.mobile_e164}</div>
            </div>
            {household ? (
              <StatusChip tone="muted">{household.name}</StatusChip>
            ) : null}
          </div>
        </Card>

        <Card className="stack">
          <div className="split">
            <h2 className="title">پت‌ها</h2>
            <Link className="button button--ghost" href="/onboarding/pet">
              افزودن پت
            </Link>
          </div>
          {petsQuery.isLoading ? <Skeleton /> : null}
          {petsQuery.isError ? (
            <Banner tone="error">فهرست پت‌ها در دسترس نیست.</Banner>
          ) : null}
          {petsQuery.data?.length === 0 ? (
            <p className="caption">هنوز پتی ثبت نشده است.</p>
          ) : null}
          {petsQuery.data?.length ? (
            <ul className="stack" aria-label="فهرست پت‌ها">
              {petsQuery.data.map((pet) => (
                <li key={pet.id}>
                  <Link className="split" href={`/pets/${pet.id}`}>
                    <span>{pet.name}</span>
                    <span className="caption">
                      {speciesLabelFa[pet.species] ?? pet.species}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </Card>

        <Card className="stack">
          <div className="split">
            <h2 className="title">آدرس‌ها</h2>
            <Link className="button button--ghost" href="/onboarding/address">
              افزودن آدرس
            </Link>
          </div>
          {addressesQuery.isLoading ? <Skeleton /> : null}
          {addressesQuery.isError ? (
            <Banner tone="error">فهرست آدرس‌ها در دسترس نیست.</Banner>
          ) : null}
          {addressesQuery.data?.length === 0 ? (
            <p className="caption">هنوز آدرسی ثبت نشده است.</p>
          ) : null}
          {addressesQuery.data?.length ? (
            <ul className="stack" aria-label="فهرست آدرس‌ها">
              {addressesQuery.data.map((address) => (
                <li className="stack" key={address.id}>
                  <span>{address.label}</span>
                  <span className="caption">
                    {address.province}، {address.city}، {address.address_line}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </Card>

        <Card className="stack">
          <h2 className="title">کیف پول</h2>
          {walletQuery.isLoading ? <Skeleton /> : null}
          {walletQuery.isError ? (
            <Banner tone="error">موجودی کیف پول در دسترس نیست.</Banner>
          ) : null}
          {walletQuery.data ? (
            <Money irr={walletQuery.data.available_balance_irr} />
          ) : null}
        </Card>

        <Card className="stack">
          <h2 className="title">پشتیبانی</h2>
          <Link className="button button--secondary" href="/support">
            درخواست‌های پشتیبانی من
          </Link>
        </Card>

        <Card className="stack">
          <h2 className="title">اعلان‌ها و حریم خصوصی</h2>
          <div className="cluster">
            <Link className="button button--secondary" href="/notifications">
              اعلان‌ها
            </Link>
            <Link className="button button--secondary" href="/privacy">
              حریم خصوصی
            </Link>
          </div>
        </Card>

        <Card className="stack">
          <h2 className="title">نشست</h2>
          <Button variant="secondary" onClick={() => setShowLogoutSheet(true)}>
            خروج از حساب
          </Button>
        </Card>

        {showLogoutSheet ? (
          <Sheet title="خروج از حساب" onClose={() => setShowLogoutSheet(false)}>
            <div className="stack">
              <p className="caption">
                با خروج از حساب، برای استفاده دوباره باید شماره موبایل خود را
                تایید کنید.
              </p>
              {logoutError ? <Banner tone="error">{logoutError}</Banner> : null}
              <div className="cluster">
                <Button
                  variant="primary"
                  loading={loggingOut}
                  onClick={() => void confirmLogout()}
                >
                  خروج
                </Button>
                <Button
                  variant="ghost"
                  disabled={loggingOut}
                  onClick={() => setShowLogoutSheet(false)}
                >
                  انصراف
                </Button>
              </div>
            </div>
          </Sheet>
        ) : null}
      </div>
    </AppShell>
  );
}
