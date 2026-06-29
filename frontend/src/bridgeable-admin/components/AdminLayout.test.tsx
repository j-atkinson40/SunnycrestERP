/**
 * AdminLayout — route-aware full-bleed (MoC A.1).
 *
 * The opt-in contract: /maps/:vertical fills the frame (full width + height,
 * no centered box); EVERY other admin route keeps the unchanged
 * `px-6 py-6 max-w-[1600px] mx-auto` box. This guards against a future edit
 * widening full-bleed to other pages (the shared-layout regression risk).
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

import { AdminLayout } from "./AdminLayout"

function mainAt(path: string): HTMLElement {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AdminLayout>
        <div>child</div>
      </AdminLayout>
    </MemoryRouter>,
  )
  return document.querySelector("main") as HTMLElement
}

describe("AdminLayout full-bleed opt-in", () => {
  it("fills the frame on the MoC vertical page (full-bleed, no 1600 cap)", () => {
    const main = mainAt("/maps/manufacturing")
    expect(main.className).toContain("flex-1")
    expect(main.className).not.toContain("max-w-[1600px]")
  })

  it("keeps the centered 1600px box on other admin pages (unchanged)", () => {
    for (const path of ["/health", "/tenants", "/migrations", "/"]) {
      const main = mainAt(path)
      expect(main.className).toContain("max-w-[1600px]")
      expect(main.className).toContain("px-6")
    }
  })
})
