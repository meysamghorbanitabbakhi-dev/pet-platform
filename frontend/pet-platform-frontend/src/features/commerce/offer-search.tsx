"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Card,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
} from "@/components/primitives";
import { getPolicies, searchOffers } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { OfferList } from "./offer-list";

const DEBOUNCE_MS = 350;

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس جستجو. دوباره تلاش کنید.";
}

export function OfferSearch() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";
  const [inputValue, setInputValue] = useState(initialQuery);
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery);

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(inputValue), DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [inputValue]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (debouncedQuery) params.set("q", debouncedQuery);
    const query = params.toString();
    router.replace(query ? `/shop/search?${query}` : "/shop/search", {
      scroll: false,
    });
  }, [debouncedQuery, router]);

  const trimmed = debouncedQuery.trim();
  const searchQuery = useQuery({
    queryKey: ["shop-search", trimmed],
    queryFn: () => searchOffers(trimmed),
    enabled: trimmed.length > 0,
  });
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setDebouncedQuery(inputValue);
  }

  const loading =
    trimmed.length > 0 && (searchQuery.isLoading || policyQuery.isLoading);

  return (
    <AppShell wide>
      <div className="stack">
        <div>
          <div className="eyebrow">فروشگاه</div>
          <h1 className="display">جستجوی محصول</h1>
        </div>
        <Card>
          <form className="stack" role="search" onSubmit={onSubmit}>
            <Input
              id="shop-search-q"
              label="جستجو در فروشگاه"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="مثلا رویال کنین یا شماره کالا"
              autoComplete="off"
              inputMode="search"
            />
          </form>
        </Card>

        <span
          role="status"
          aria-live="polite"
          style={{
            position: "absolute",
            width: 1,
            height: 1,
            overflow: "hidden",
            clip: "rect(0 0 0 0)",
            whiteSpace: "nowrap",
          }}
        >
          {trimmed.length === 0 || loading
            ? ""
            : searchQuery.isError
              ? "جستجو ناموفق بود"
              : `${searchQuery.data?.page.total ?? 0} نتیجه یافت شد`}
        </span>

        {trimmed.length === 0 ? (
          <EmptyState
            title="عبارتی برای جستجو وارد کنید"
            body="می‌توانید بر اساس نام فارسی محصول یا شماره کالا جستجو کنید."
          />
        ) : loading ? (
          <div className="grid grid--two">
            {[0, 1, 2, 3].map((index) => (
              <Card key={index} className="stack">
                <Skeleton />
                <Skeleton />
              </Card>
            ))}
          </div>
        ) : searchQuery.isError ? (
          <ErrorState
            title="جستجو ناموفق بود"
            body={errorText(searchQuery.error)}
            action={
              <button
                type="button"
                className="button button--secondary"
                onClick={() => searchQuery.refetch()}
              >
                تلاش مجدد
              </button>
            }
          />
        ) : searchQuery.data && searchQuery.data.items.length === 0 ? (
          <EmptyState
            title="نتیجه‌ای یافت نشد"
            body={`برای «${trimmed}» محصولی پیدا نشد. عبارت دیگری را امتحان کنید.`}
          />
        ) : searchQuery.data && policyQuery.data ? (
          <OfferList
            offers={searchQuery.data.items}
            policy={policyQuery.data}
          />
        ) : null}
      </div>
    </AppShell>
  );
}
