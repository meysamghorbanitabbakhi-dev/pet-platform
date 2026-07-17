import { describe, expect, it } from "vitest";
import {
  formatDeliveryCommitment,
  formatTomanFromIrr,
  tomanFromIrr,
} from "./format";

describe("Iran-first formatting", () => {
  it("derives toman display from IRR by division by 10 and labels the unit", () => {
    expect(tomanFromIrr(4_800_000)).toBe(480_000);
    expect(formatTomanFromIrr(4_800_000)).toContain("تومان");
    expect(formatTomanFromIrr(4_800_000)).toContain("۴۸۰");
  });

  it("keeps the exact 366 hour delivery commitment", () => {
    expect(formatDeliveryCommitment(366)).toBe("۳۶۶ ساعت");
  });
});
