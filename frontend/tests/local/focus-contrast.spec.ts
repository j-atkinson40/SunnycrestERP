/**
 * Contrast on every Focus mode — the measurement, before any fix.
 *
 * ⚠️ **IT MEASURES WHAT IS ON THE GLASS, NOT WHAT THE TOKENS SAY.** The
 * question is what reaches the reader's eye through a dimmed, blurred
 * backdrop, and a token's nominal value cannot answer that. Each Focus is
 * opened for real and photographed; `focus-contrast.mjs` reads the pixels.
 *
 * ⚠️ **EVERY REGISTERED FOCUS, NOT THE FIVE I REMEMBERED.** The registry
 * holds TWELVE; five is the number of MODES. Two carry a bespoke core
 * (`weekly-payroll`, `union-form`) and the rest fall through to the
 * mode-generic renderer, so the modes are covered by whichever Focus
 * exercises them.
 */
import { expect, test } from "@playwright/test"

const SLUG = process.env.PW_SLUG ?? "testco"
const SHOTS = "tests/local/shots/contrast"

/** Every registered Focus id, with the credentials that can open it.
 *  ⚠️ Read off `focus-registry.ts`, not recalled. */
const FOCUSES: { id: string; mode: string; as: "admin" | "payroll"; scope?: string }[] = [
  { id: "weekly-payroll", mode: "singleRecord", as: "payroll", scope: "week_end" },
  { id: "union-form", mode: "singleRecord", as: "payroll", scope: "period" },
  { id: "funeral-scheduling", mode: "kanban", as: "admin" },
  { id: "decision-triage", mode: "triageQueue", as: "admin" },
  { id: "books-review", mode: "triageQueue", as: "admin" },
  { id: "month-end-close", mode: "triageQueue", as: "admin" },
  { id: "expense-categorization", mode: "triageQueue", as: "admin" },
  { id: "cash-receipts", mode: "triageQueue", as: "admin" },
  { id: "test-kanban", mode: "kanban", as: "admin" },
  { id: "test-single-record", mode: "singleRecord", as: "admin" },
  { id: "test-edit-canvas", mode: "editCanvas", as: "admin" },
  { id: "test-triage-queue", mode: "triageQueue", as: "admin" },
  { id: "test-matrix", mode: "matrix", as: "admin" },
]

const WHO = {
  payroll: {
    email: process.env.PW_WALK_EMAIL ?? "susan.walkthrough@testco.example.com",
    password: process.env.PW_WALK_PASSWORD ?? "WalkThrough123!",
  },
  admin: {
    email: process.env.PW_ADMIN_EMAIL ?? "admin@testco.com",
    password: process.env.PW_ADMIN_PASSWORD ?? "TestAdmin123!",
  },
}

test.describe.configure({ mode: "serial" })

async function signIn(page: import("@playwright/test").Page, as: "admin" | "payroll") {
  await page.context().clearCookies()
  await page.goto(`/?slug=${SLUG}`)
  await page.evaluate(() => {
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
  })
  await page.goto(`/?slug=${SLUG}`)
  await page.getByLabel(/email/i).fill(WHO[as].email)
  await page.getByLabel(/password/i).fill(WHO[as].password)
  await page.getByRole("button", { name: /sign in/i }).click()
  await page.waitForURL(/\/(home|note|dashboard)/, { timeout: 30_000 })
}

for (const f of FOCUSES) {
  test(`contrast · ${f.id} (${f.mode})`, async ({ page }) => {
    await signIn(page, f.as)

    const scope =
      f.scope === "week_end"
        ? "&week_end=2026-10-31"
        : f.scope === "period"
          ? "&period=2026-10"
          : ""
    await page.goto(`/home?focus=${f.id}${scope}`)

    // ⚠️ WAIT FOR THE DIALOG, NOT A TIMEOUT. A screenshot taken mid-open
    // photographs the backdrop and measures the backdrop — which is the
    // failure PR C made three times.
    const core = page.locator("[data-slot='focus-core']")
    await expect(core).toBeVisible({ timeout: 20_000 })
    // Let the open animation settle so the shot is of the resting state.
    await page.waitForTimeout(600)

    // ⚠️ **TEXT ELEMENTS, ONE BY ONE — NOT ROWS, NOT THE WHOLE BOX.**
    //
    // Two earlier versions of this measurement were wrong, in the same way
    // and for the same reason: the instrument answered a nearby question.
    //   * The full viewport included the dimmed note BEHIND the Focus, whose
    //     text is supposed to be unreadable — reporting the backdrop working
    //     as designed as a defect, and putting a Focus I had measured at
    //     14.49:1 below AA.
    //   * Clipping to the core's box then scanned ROWS, taking each row's
    //     darkest pixel — which at the card's rounded corners is the
    //     backdrop outside it. Every row came back at 4.53, the card edge,
    //     not the text.
    //
    // So each text element is photographed on its own. Within one element's
    // box the darkest pixel is its glyphs and the lightest is the surface
    // directly behind them, which is the comparison AA is defined over.
    const box = await core.boundingBox()
    if (!box) throw new Error(`${f.id}: the focus core has no box to measure`)

    const texts = await core.evaluate((root) => {
      const out: { sel: string; text: string }[] = []
      let n = 0
      for (const el of Array.from(root.querySelectorAll<HTMLElement>("*"))) {
        // Leaf elements only: a parent's box contains its children's
        // surfaces and would mix two comparisons into one.
        if (el.children.length > 0) continue
        const t = (el.textContent ?? "").trim()
        if (t.length < 3) continue
        const r = el.getBoundingClientRect()
        if (r.width < 8 || r.height < 8) continue
        const cs = getComputedStyle(el)
        if (cs.visibility === "hidden" || cs.opacity === "0") continue
        el.setAttribute("data-contrast-probe", String(n))
        out.push({ sel: `[data-contrast-probe="${n}"]`, text: t.slice(0, 40) })
        n += 1
        if (n >= 40) break
      }
      return out
    })

    const fs = await import("node:fs/promises")
    await fs.mkdir(`${SHOTS}/${f.id}`, { recursive: true })
    for (const [i, probe] of texts.entries()) {
      await page
        .locator(probe.sel)
        .screenshot({ path: `${SHOTS}/${f.id}/${String(i).padStart(2, "0")}.png` })
    }
    await fs.writeFile(
      `${SHOTS}/${f.id}/labels.json`,
      JSON.stringify(texts.map((t) => t.text), null, 1),
    )
    await page.screenshot({
      path: `${SHOTS}/${f.id}.png`,
      clip: { x: box.x, y: box.y, width: box.width, height: box.height },
    })
    // eslint-disable-next-line no-console
    console.log(`PROBES ${f.id} ${texts.length}`)
  })
}
