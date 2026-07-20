import { describe, expect, it } from "vitest";
import { checkInIdempotencyKey } from "./journey-idempotency";

describe("checkInIdempotencyKey", () => {
  it("is deterministic for the same journey, step, and answer, so a resubmission replays safely", () => {
    const first = checkInIdempotencyKey("journey-1", "week1", "on_track");
    const second = checkInIdempotencyKey("journey-1", "week1", "on_track");

    expect(first).toBe(second);
  });

  it("produces a different key when the answer differs, never colliding with a different response", () => {
    const onTrack = checkInIdempotencyKey("journey-1", "week1", "on_track");
    const offTrack = checkInIdempotencyKey("journey-1", "week1", "off_track");

    expect(onTrack).not.toBe(offTrack);
  });

  it("produces a different key when the step differs, even for the same answer", () => {
    const week1 = checkInIdempotencyKey("journey-1", "week1", "on_track");
    const week2 = checkInIdempotencyKey("journey-1", "week2", "on_track");

    expect(week1).not.toBe(week2);
  });

  it("produces a different key for a different journey with otherwise identical step/answer", () => {
    const journeyA = checkInIdempotencyKey("journey-a", "week1", "on_track");
    const journeyB = checkInIdempotencyKey("journey-b", "week1", "on_track");

    expect(journeyA).not.toBe(journeyB);
  });

  it("never exceeds the backend's 255-character Idempotency-Key bound", () => {
    const key = checkInIdempotencyKey("j".repeat(200), "k".repeat(200), "a");

    expect(key.length).toBeLessThanOrEqual(255);
  });
});
