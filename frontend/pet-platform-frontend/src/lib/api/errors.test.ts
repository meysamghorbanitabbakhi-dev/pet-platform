import { describe, expect, it } from "vitest";
import { mapApiError } from "./errors";

describe("mapApiError", () => {
  it("maps a 409 conflict to a specific, actionable message instead of the generic connectivity fallback", () => {
    const error = mapApiError(409, "offer offer-1 is unavailable");

    expect(error.message).not.toBe("خطا در ارتباط با سرویس.");
    expect(error.status).toBe(409);
    expect(error.detail).toBe("offer offer-1 is unavailable");
  });

  it("still falls back to a generic message for an unmapped status", () => {
    const error = mapApiError(500, undefined);

    expect(error.message).toBe("خطا در ارتباط با سرویس.");
    expect(error.status).toBe(500);
  });
});
