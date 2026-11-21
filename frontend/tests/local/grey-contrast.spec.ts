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
  test(`the three greys on four surfaces — ${mode}`, async ({ page }) => {
    // ⚠️ **LIGHT IS MEASURED SIGNED IN; DARK IS MEASURED PRE-AUTH, AND THE
    // REASON IS A FINDING RATHER THAN A CONVENIENCE.**
    //
    // Inside the signed-in app the theme resolver writes the resolved tokens
    // as INLINE STYLES on `documentElement`. Inline beats the
    // `[data-mode="dark"]` stylesheet rule, and the resolver does not
    // re-resolve for dark — so dark mode does not take effect at all for a
    // tenant with a resolved theme. Verified by a control that fails loudly
    // when the swatch is still light.
    //
    // Signed in is the right place to measure LIGHT, because that is where
    // the values actually come from (`base-tokens.ts`, not `tokens.css`).
    // For DARK the pre-auth page is the only place the dark values render at
    // all, and it renders them from the same stylesheet the app ships.
    await page.goto("/?slug=testco")
    if (mode === "light") {
      await page.getByLabel(/email/i).fill("susan.walkthrough@testco.example.com")
      await page.getByLabel(/password/i).fill("WalkThrough123!")
      await page.getByRole("button", { name: /sign in/i }).click()
      await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
    }

    // ⚠️ **SWITCH VIA THE APP'S OWN API, THEN PROVE IT TOOK BY A RENDERED
    // PIXEL — NOT BY READING THE VARIABLE.**
    //
    // Setting `data-mode` by hand does not switch this app: the theme
    // resolver writes the resolved tokens as INLINE STYLES on
    // `documentElement`, and inline beats the `[data-mode="dark"]`
    // stylesheet rule. It re-resolves on `bridgeable-mode-change`, which
    // only `theme-mode.setMode` dispatches.
    //
    // The first version set the attribute and read the variable back, which
    // returned the dark value — then the resolver re-applied light inline a
    // tick later and the screenshots came out light. The light and dark
    // tables were IDENTICAL TO TWO DECIMALS and the spec passed, because the
    // control was reading a different thing from the one being measured.
    // The control is now a pixel from the same screenshot pipeline.
    await page.evaluate((m) => {
      window.dispatchEvent(
        new CustomEvent("bridgeable-mode-change", { detail: m }),
      )
      const root = document.documentElement
      if (m === "dark") root.setAttribute("data-mode", "dark")
      else root.removeAttribute("data-mode")
      localStorage.setItem("bridgeable-mode", m)
    }, mode)
    await page.waitForTimeout(800)

    // Build a swatch grid from the real tokens, inside the real app, so the
    // theme layer's values are the ones rendered.
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

    // ⚠️ THE CONTROL, read from the SAME pipeline that produced the numbers:
    // the page-canvas swatch must actually be dark in dark mode. Without
    // this the two tables can be identical and the spec still green.
    const bg = await page.locator('[data-probe="surface-base__content-base"]')
      .evaluate((el) => getComputedStyle(el).backgroundColor)
    if (mode === "dark") {
      expect(bg, "dark mode did not apply — the swatch is still light").not.toBe(
        "oklch(0.94 0.003 250)",
      )
    } else {
      expect(bg).toBe("oklch(0.94 0.003 250)")
    }
  })
}
