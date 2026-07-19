import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// scripts/e2e-real-backend.mjs writes the most recently issued OTP code
// here every time the backend's dev-console fallback logs one -- there is
// no API response field carrying it (see the fallback's own source,
// app/integrations/otp/dev_console.py). Polls for a *fresh* entry (written
// after `since`) matching the given mobile, rather than reading whatever is
// currently on disk, so a stale code from an earlier test/run is never
// mistaken for the one just requested.
// process.cwd(), not import.meta.dirname: Playwright's own module loader
// does not expose import.meta in this context.
const otpLogPath = resolve(process.cwd(), ".e2e-real-backend-otp.json");

export async function waitForOtpCode(
  mobile: string,
  { since, timeoutMs = 15_000, intervalMs = 250 } = { since: Date.now() },
): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const entry = JSON.parse(readFileSync(otpLogPath, "utf8")) as {
        mobile: string;
        code: string;
        capturedAt: number;
      };
      if (entry.mobile === mobile && entry.capturedAt >= since) {
        return entry.code;
      }
    } catch {
      // file not written yet -- fine, keep polling
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, intervalMs));
  }
  throw new Error(`timed out waiting for an OTP code for ${mobile}`);
}
