"use client";

import { useSyncExternalStore } from "react";
import { readCompareList, subscribeCompareList } from "@/lib/compare-list";

const initialCompareList: string[] = [];

let compareListSnapshot = initialCompareList;

function sameList(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  return left.every((id, index) => id === right[index]);
}

function getCompareListSnapshot() {
  const next = readCompareList();
  if (sameList(compareListSnapshot, next)) return compareListSnapshot;
  compareListSnapshot = next;
  return compareListSnapshot;
}

export function useCompareListSnapshot() {
  return useSyncExternalStore(
    subscribeCompareList,
    getCompareListSnapshot,
    () => initialCompareList,
  );
}
