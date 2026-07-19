import { defineConfig, devices } from "@playwright/test";

// Runs tests/e2e-real-backend against a genuinely live FastAPI + Postgres +
// Redis stack (started by scripts/e2e-real-backend.mjs), not the
// GATE_FIXTURE_MODE in-memory mock the default playwright.config.ts uses.
// Deliberately a separate config/testDir rather than a project inside the
// default one: the two modes need different webServer wiring (no
// GATE_FIXTURE_MODE env, a real backend origin) and should never be
// accidentally run together in one pass.
const PORT = Number(process.env.PORT ?? 3100);
const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8010);
const DIST_DIR = process.env.NEXT_DIST_DIR ?? ".next-e2e-real-backend";

export default defineConfig({
  testDir: "./tests/e2e-real-backend",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
    locale: "fa-IR",
    timezoneId: "Asia/Tehran",
  },
  webServer: {
    // The standalone server.js directly, not `next dev` or `next start`:
    // Next 16 locks dev-server state per project directory
    // (.next/dev/lock), not per port, so a second `next dev` here would
    // refuse to start whenever a developer already has their own `pnpm dev`
    // running; and `next start` does not work with `output: standalone`.
    // scripts/e2e-real-backend.mjs builds and stages this before Playwright
    // starts, using NEXT_DIST_DIR to keep the output isolated from the
    // developer's own .next.
    command: `node ${DIST_DIR}/standalone/server.js`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      PORT: String(PORT),
      HOSTNAME: "127.0.0.1",
      NEXT_PUBLIC_API_BASE_URL: `http://127.0.0.1:${BACKEND_PORT}`,
    },
  },
  projects: [
    {
      name: "chromium-real-backend",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
