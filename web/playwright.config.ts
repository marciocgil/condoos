import { defineConfig, devices } from "@playwright/test";

// E2E tests run against the docker compose stack (web on :3000, Mailpit on :8025).
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    // Optional: use a system Chromium instead of the one downloaded by `playwright install`.
    launchOptions: process.env.PW_CHROMIUM_PATH
      ? { executablePath: process.env.PW_CHROMIUM_PATH }
      : {},
  },
  projects: [
    { name: "sindico-mobile", use: { ...devices["iPhone 13"], browserName: "chromium" } },
    { name: "admin-desktop", use: { ...devices["Desktop Chrome"] } },
  ],
});
