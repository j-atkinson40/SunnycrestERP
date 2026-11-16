/**
 * LOCAL Playwright project — the Payroll 5a walkthrough.
 *
 * ⚠️ **SEPARATE FILE, NOT A PROJECT INSIDE `playwright.config.ts`.** That
 * config points every project at the STAGING deployment, and this walk must
 * never run there: it enters hours, records decisions and approves a week. A
 * second `projects` entry would be one `--project` typo away from doing all of
 * that to staging's data.
 *
 * Expects both servers already running, and the database seeded by
 * `backend/scripts/seed_week44_walkthrough.py`:
 *
 *   PW_WEEK_ID=<week id from the seed> \
 *   PW_TOKEN=<token minted locally> \
 *   npx playwright test -c playwright.local.config.ts
 */
import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/local",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  outputDir: "tests/local/output",
  use: {
    baseURL: process.env.PW_BASE_URL ?? "http://127.0.0.1:5199",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: "local-chromium" }],
})
