/** What actually puts the signed-in app into dark mode. */
import { test } from "@playwright/test"

for (const scheme of ["light", "dark"] as const) {
  test.describe(`os prefers-color-scheme: ${scheme}`, () => {
    test.use({ colorScheme: scheme })
    test(`signed-in app`, async ({ page }) => {
      await page.goto("/?slug=testco")
      await page.getByLabel(/email/i).fill("susan.walkthrough@testco.example.com")
      await page.getByLabel(/password/i).fill("WalkThrough123!")
      await page.getByRole("button", { name: /sign in/i }).click()
      await page.waitForURL(/\/(home|note)/, { timeout: 30_000 })
      await page.waitForTimeout(800)
      const v = await page.evaluate(() => ({
        dataMode: document.documentElement.getAttribute("data-mode"),
        surfaceBase: getComputedStyle(document.documentElement)
          .getPropertyValue("--surface-base").trim(),
        bodyBg: getComputedStyle(document.body).backgroundColor,
        inlineOverrides: (document.documentElement.getAttribute("style") ?? "")
          .includes("--surface-base"),
      }))
      console.log(`SCHEME=${scheme} ` + JSON.stringify(v))
    })
  })
}
