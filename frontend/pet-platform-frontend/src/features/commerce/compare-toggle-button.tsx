"use client";

import Link from "next/link";
import { Button } from "@/components/primitives";
import { MAX_COMPARE_ITEMS, toggleCompareItem } from "@/lib/compare-list";
import { useCompareListSnapshot } from "./use-compare-list";

export function CompareToggleButton({ offerId }: { offerId: string }) {
  const compareList = useCompareListSnapshot();
  const inList = compareList.includes(offerId);
  const atCapacity = !inList && compareList.length >= MAX_COMPARE_ITEMS;
  const otherCount = compareList.filter((id) => id !== offerId).length;

  return (
    <div className="cluster">
      <Button
        variant="secondary"
        disabled={atCapacity}
        onClick={() => toggleCompareItem(offerId)}
      >
        {inList ? "حذف از مقایسه" : "افزودن به مقایسه"}
      </Button>
      {otherCount > 0 ? (
        <Link
          className="button button--ghost"
          href={`/shop/offer/${offerId}/compare`}
        >
          مشاهده مقایسه ({otherCount + 1})
        </Link>
      ) : null}
    </div>
  );
}
