import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PORT ?? 3000);

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "on-first-retry",
    locale: "fa-IR",
    timezoneId: "Asia/Tehran",
  },
  webServer: {
    command: `pnpm dev -H 127.0.0.1 -p ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    env: {
      GATE_FIXTURE_MODE: "1",
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000",
    },
  },
  projects: [
    {
      name: "chromium-320",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 320, height: 780 },
      },
    },
    {
      name: "chromium-390",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
      },
    },
    {
      name: "chromium-768",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      name: "chromium-1024",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1024, height: 900 },
      },
    },
  ],
});
