import { beforeEach, describe, expect, it } from "vitest";
import {
  MAX_COMPARE_ITEMS,
  clearCompareList,
  isInCompareList,
  readCompareList,
  toggleCompareItem,
} from "./compare-list";

describe("compare-list local store", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("adds and removes an offer id by toggling", () => {
    expect(readCompareList()).toEqual([]);

    toggleCompareItem("offer-1");
    expect(readCompareList()).toEqual(["offer-1"]);
    expect(isInCompareList("offer-1")).toBe(true);

    toggleCompareItem("offer-1");
    expect(readCompareList()).toEqual([]);
    expect(isInCompareList("offer-1")).toBe(false);
  });

  it("refuses to add beyond the bounded cap, never silently evicting an existing item", () => {
    for (let i = 0; i < MAX_COMPARE_ITEMS; i += 1) {
      toggleCompareItem(`offer-${i}`);
    }
    expect(readCompareList()).toHaveLength(MAX_COMPARE_ITEMS);

    toggleCompareItem("offer-overflow");

    expect(readCompareList()).toHaveLength(MAX_COMPARE_ITEMS);
    expect(readCompareList()).not.toContain("offer-overflow");
  });

  it("still allows removing an existing item while at capacity", () => {
    for (let i = 0; i < MAX_COMPARE_ITEMS; i += 1) {
      toggleCompareItem(`offer-${i}`);
    }

    toggleCompareItem("offer-0");

    expect(readCompareList()).toHaveLength(MAX_COMPARE_ITEMS - 1);
    expect(readCompareList()).not.toContain("offer-0");
  });

  it("clears the whole list", () => {
    toggleCompareItem("offer-1");
    toggleCompareItem("offer-2");

    clearCompareList();

    expect(readCompareList()).toEqual([]);
  });

  it("never stores anything but plain string offer ids", () => {
    toggleCompareItem("offer-1");
    const raw = window.localStorage.getItem("pet-platform.compare-list.v1");
    expect(raw).toBe(JSON.stringify(["offer-1"]));
  });
});
