/**
 * AdminLayout — route-aware full-bleed (MoC A.1 → hierarchy polish).
 *
 * The opt-in contract: the THREE MoC hierarchy levels fill the frame — the
 * platform landing at the EXACT root ("/"), the vertical maps
 * (/maps/:vertical), the tenant maps (/maps/:vertical/:tenantSlug); EVERY
 * other admin route keeps the unchanged `px-6 py-6 max-w-[1600px] mx-auto`
 * box. The root match is exact, never a prefix — the boundary pins guard the
 * greedy-match regression.
 *
 * (The pre-polish "/ is boxed" pin RETIRED with the landing becoming a map
 * level in H-2; the boxed contract now pins the operational set. Also fixed:
 * the old helper queried the FIRST accumulated <main> across renders — each
 * assertion now scopes to its own render's container.)
 */
import { describe, expect, it, vi } from "vitest"
import { render } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

vi.mock("../lib/admin-auth-context", () => ({
  useAdminAuth: () => ({ user: { id: "u" }, loading: false }),
}))
vi.mock("./AdminHeader", () => ({ AdminHeader: () => null }))
vi.mock("./EnvironmentBanner", () => ({ EnvironmentBanner: () => null }))
vi.mock("./AdminCommandBar", () => ({
  AdminCommandBarProvider: ({ children }: { children: React.ReactNode }) => children,
}))

import { AdminLayout, isFullBleedRoute } from "./AdminLayout"

function mainAt(path: string): HTMLElement {
  const { container } = render(
    <MemoryRouter initialEntries={[path]}>
      <AdminLayout>
        <div>child</div>
      </AdminLayout>
    </MemoryRouter>,
  )
  return container.querySelector("main") as HTMLElement
}

describe("AdminLayout full-bleed opt-in", () => {
  it("fills the frame on all THREE MoC hierarchy levels", () => {
    for (const path of [
      "/",                                  // the platform landing (polish)
      "/bridgeable-admin/",                 // …both entry forms
      "/maps/manufacturing",                // the vertical map
      "/maps/manufacturing/testco",         // the tenant map
    ]) {
      const main = mainAt(path)
      expect(main.className, path).toContain("flex-1")
      expect(main.className, path).not.toContain("max-w-[1600px]")
    }
  })

  it("keeps the centered 1600px box on other admin pages (the non-greedy boundary)", () => {
    for (const path of ["/health", "/tenants", "/migrations", "/studio", "/bridgeable-admin/health"]) {
      const main = mainAt(path)
      expect(main.className, path).toContain("max-w-[1600px]")
      expect(main.className, path).toContain("px-6")
    }
  })

  it("isFullBleedRoute: the root match is EXACT, never a prefix", () => {
    expect(isFullBleedRoute("/")).toBe(true)
    expect(isFullBleedRoute("/bridgeable-admin")).toBe(true)
    expect(isFullBleedRoute("/bridgeable-admin/")).toBe(true)
    expect(isFullBleedRoute("/health")).toBe(false)     // starts with "/" — not matched
    expect(isFullBleedRoute("/telemetry")).toBe(false)
    expect(isFullBleedRoute("/bridgeable-admin/staging")).toBe(false)
  })
})
