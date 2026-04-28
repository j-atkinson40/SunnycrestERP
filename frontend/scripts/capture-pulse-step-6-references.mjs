#!/usr/bin/env node
/**
 * Capture Pulse Step 6 reference implementation screenshots.
 *
 * Phase W-4a Step 6 Commit 6 — captures the canonical 5-viewport
 * matrix (mobile + tablet + desktop common + desktop FHD + 4K)
 * × 2 modes (light + dark) = 10 screenshots into
 * `docs/design-references/pulse-step-6/` for §13.8 reference
 * implementations.
 *
 * Prerequisites:
 *   - Frontend dev server running on http://localhost:5173
 *   - Backend dev server running on http://localhost:8000 with
 *     testco tenant seeded (admin@testco.com / TestAdmin123!) +
 *     work_areas set per D5 canonical Sunnycrest dispatcher
 *     composition
 *
 * Usage:
 *   node frontend/scripts/capture-pulse-step-6-references.mjs
 */

import { chromium } from "playwright"
import { writeFile, mkdir } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const REPO_ROOT = resolve(__dirname, "..", "..")
const OUTPUT_DIR = resolve(REPO_ROOT, "docs/design-references/pulse-step-6")

const FRONTEND_URL = "http://localhost:5173"
const BACKEND_URL = "http://localhost:8000"
const TENANT_SLUG = "testco"
const ADMIN_EMAIL = "admin@testco.com"
const ADMIN_PASSWORD = "TestAdmin123!"

const VIEWPORTS = [
  { id: "mobile", width: 375, height: 667, label: "Mobile portrait — scroll mode" },
  { id: "tablet", width: 768, height: 1024, label: "Tablet portrait — viewport-fit, 4-col" },
  { id: "desktop-common", width: 1440, height: 900, label: "Desktop common — viewport-fit, 6-col, canonical baseline" },
  { id: "desktop-fhd", width: 1920, height: 1080, label: "Desktop FHD — viewport-fit, scale up" },
  { id: "4k", width: 2560, height: 1440, label: "4K display — scale ceiling + breathing room" },
]

const MODES = ["light", "dark"]


async function loginAndStoreTokens(page) {
  // Hit backend login endpoint, store tokens in localStorage
  const res = await page.request.post(`${BACKEND_URL}/api/v1/auth/login`, {
    headers: {
      "Content-Type": "application/json",
      "X-Company-Slug": TENANT_SLUG,
    },
    data: {
      email: ADMIN_EMAIL,
      password: ADMIN_PASSWORD,
    },
  })
  if (!res.ok()) {
    throw new Error(`Login failed: ${res.status()} ${await res.text()}`)
  }
  const data = await res.json()
  await page.evaluate(
    ({ access_token, refresh_token, slug }) => {
      localStorage.setItem("access_token", access_token)
      localStorage.setItem("refresh_token", refresh_token)
      localStorage.setItem("company_slug", slug)
    },
    { access_token: data.access_token, refresh_token: data.refresh_token, slug: TENANT_SLUG },
  )
}


async function captureViewport(browser, viewport, mode) {
  const filename = `pulse-${viewport.id}-${mode}.png`
  const filepath = resolve(OUTPUT_DIR, filename)
  console.log(`Capturing ${filename} (${viewport.width}×${viewport.height}, ${mode} mode)...`)

  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    colorScheme: mode,
    // Disable animations for stable captures.
    reducedMotion: "reduce",
  })
  const page = await context.newPage()
  // Bootstrap auth + tenant slug at the frontend origin so localStorage
  // is set under the right origin before navigation.
  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: "domcontentloaded" })
  await loginAndStoreTokens(page)
  // Set color scheme via data-mode attribute too (client-side override
  // for our explicit mode toggle, in addition to the colorScheme media
  // emulation above).
  await page.evaluate((m) => {
    if (m === "dark") {
      document.documentElement.setAttribute("data-mode", "dark")
    } else {
      document.documentElement.removeAttribute("data-mode")
    }
  }, mode)
  // Navigate to /home + wait for Pulse to settle.
  await page.goto(`${FRONTEND_URL}/home`, { waitUntil: "networkidle" })
  // Re-apply mode after navigation (mode attribute can clear on nav).
  await page.evaluate((m) => {
    if (m === "dark") {
      document.documentElement.setAttribute("data-mode", "dark")
    } else {
      document.documentElement.removeAttribute("data-mode")
    }
  }, mode)
  // Give Pulse composition fetch + render time to settle.
  await page.waitForSelector('[data-slot="pulse-surface"][data-state="ready"]', {
    timeout: 10000,
  })
  // Allow a beat for container queries + transitions to fully resolve.
  await page.waitForTimeout(800)
  await page.screenshot({
    path: filepath,
    fullPage: false,
    type: "png",
  })
  await context.close()
  console.log(`  → ${filepath}`)
}


async function main() {
  await mkdir(OUTPUT_DIR, { recursive: true })
  console.log(`Output directory: ${OUTPUT_DIR}`)
  const browser = await chromium.launch({ headless: true })
  try {
    for (const viewport of VIEWPORTS) {
      for (const mode of MODES) {
        await captureViewport(browser, viewport, mode)
      }
    }
  } finally {
    await browser.close()
  }
  console.log(`\n✓ Captured ${VIEWPORTS.length * MODES.length} screenshots.`)
}

main().catch((err) => {
  console.error("Capture failed:", err)
  process.exit(1)
})
