/**
 * The three greys, on all four surfaces, in both modes — measured on LIVE
 * elements inside the signed-in app.
 *
 * ⚠️ **SIGNED IN, BECAUSE THAT IS WHERE THE VALUES COME FROM.** The tenant
 * theme re-declares these tokens at runtime from `base-tokens.ts`; a check on
 * the pre-auth page reads `tokens.css` and agrees with itself while being
 * about the wrong document. That is exactly how the previous token change
 * appeared to work and did not.
 *
 * ⚠️ **REAL ELEMENTS, NOT COMPUTED COLOUR PAIRS.** The point is what reaches
 * the eye: each grey is rendered on each surface and the pixels are read.
 */
import { expect, test } from "@playwright/test"

const SHOTS = "tests/local/shots/greys"
const GREYS = ["content-base", "content-muted", "content-subtle"] as const
const SURFACES = ["surface-base", "surface-sunken", "surface-elevated", "surface-raised"] as const

for (const mode of ["light", "dark"] as const) {
  // ⚠️ **THE MODE IS SET BY THE OS PREFERENCE, BEFORE THE PAGE LOADS.**
  //
  // index.html's inline boot script sets `data-mode="dark"` from
  // `localStorage['bridgeable-mode']` or `prefers-color-scheme` BEFORE React
  // hydrates, and the theme resolver then writes the tokens for THAT mode as
  // inline styles on documentElement. Flipping the attribute afterwards does
  // nothing, because the resolver does not re-resolve and inline beats the
  // stylesheet.
  //
  // ⚠️ **AN EARLIER VERSION OF THIS SPEC CONCLUDED DARK MODE WAS BROKEN IN
  // THE SIGNED-IN APP. IT IS NOT.** Playwright defaults to
  // `colorScheme: "light"`, so the app never booted dark and every attempt
  // to toggle it afterwards hit the post-load path, which genuinely does not
  // work. James renders dark every day. The finding was true of the toggle
  // and false of the app, and it was reported as the latter.
  test.describe(`${mode} mode`, () => {
    test.use({ colorScheme: mode })

    test(`the three greys on four surfaces — signed in, ${mode}`, async ({ page }) => {
      await page.goto("/?slug=testco")
      await page.getByLabel(/email/i).fill("susan.walkthrough@testco.example.com")
      await page.getByLabel(/password/i).fill("WalkThrough123!")
      await page.getByRole("button", { name: /sign in/i }).click()
      await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
      await page.waitForTimeout(600)

      // ⚠️ THE CONTROL, BEFORE ANY MEASURING: the app must actually be in the
      // mode this test claims. Read from the rendered page canvas, which is
      // the same thing the swatches below are made of.
      const canvas = await page.evaluate(
        () => getComputedStyle(document.body).backgroundColor,
      )
      const EXPECT = mode === "dark" ? "oklch(0.13 0.004 255)" : "oklch(0.94 0.003 250)"
      expect(canvas, `the signed-in app did not boot in ${mode} mode`).toBe(EXPECT)

      await page.evaluate(
        ({ greys, surfaces }) => {
          const host = document.createElement("div")
          host.id = "grey-probe"
          host.style.cssText =
            "position:fixed;inset:0;z-index:99999;display:grid;" +
            `grid-template-columns:repeat(${greys.length},1fr);`
          for (const s of surfaces) {
            for (const g of greys) {
              const cell = document.createElement("div")
              cell.setAttribute("data-probe", `${s}__${g}`)
              cell.style.cssText =
                `background:var(--${s});color:var(--${g});` +
                "font:600 20px system-ui;padding:14px;"
              cell.textContent = "Agh"
              host.appendChild(cell)
            }
          }
          document.body.appendChild(host)
        },
        { greys: GREYS, surfaces: SURFACES },
      )

      const fs = await import("node:fs/promises")
      await fs.mkdir(`${SHOTS}/${mode}`, { recursive: true })
      for (const s of SURFACES) {
        for (const g of GREYS) {
          await page
            .locator(`[data-probe="${s}__${g}"]`)
            .screenshot({ path: `${SHOTS}/${mode}/${s}__${g}.png` })
        }
      }
      expect(await page.locator("[data-probe]").count()).toBe(
        GREYS.length * SURFACES.length,
      )
    })
  })
}
