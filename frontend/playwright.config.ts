import { defineConfig, devices } from "@playwright/test";

const STAGING_FRONTEND = "https://determined-renewal-staging.up.railway.app";

export default defineConfig({
  testDir: "./tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  globalTeardown: "./tests/e2e/global-teardown.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 1,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: "tests/e2e/report", open: "never" }],
    ["./tests/e2e/incident-reporter.ts"],
  ],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: STAGING_FRONTEND,
    trace: "on-first-retry",
    screenshot: "on",
    video: "on",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  outputDir: "tests/e2e/screenshots",
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 5"] },
    },
  ],
});
