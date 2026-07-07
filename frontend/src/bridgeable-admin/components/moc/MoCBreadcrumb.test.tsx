/**
 * MoCBreadcrumb (H-3) — the spine's derivation per level.
 *
 * Route-derived by construction (props come from useParams at the call sites,
 * so a COLD DEEP-LINK renders the same crumb — the page tests pin that); these
 * pin the segment/link contract: vertical level = Platform › <Vertical>
 * (platform linked, vertical current); tenant level = all three (platform +
 * vertical linked, tenant current); labels come from the verticals registry.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { MoCBreadcrumb } from "./MoCBreadcrumb"

function renderCrumb(props: { vertical: string; tenantLabel?: string }) {
  return render(
    <MemoryRouter>
      <MoCBreadcrumb {...props} />
    </MemoryRouter>,
  )
}

describe("MoCBreadcrumb", () => {
  it("vertical level: Platform (linked) › Vertical (current)", () => {
    renderCrumb({ vertical: "manufacturing" })
    const platform = screen.getByTestId("moc-crumb-platform")
    expect(platform.getAttribute("href")).toContain("/")
    const current = screen.getByTestId("moc-crumb-current")
    expect(current.textContent).toBe("Manufacturing")   // registry label, not slug
    expect(current.tagName).toBe("SPAN")                // current = not a link
    expect(screen.queryByTestId("moc-crumb-vertical")).toBeNull()
  })

  it("tenant level: Platform › Vertical (both linked) › Tenant (current)", () => {
    renderCrumb({ vertical: "manufacturing", tenantLabel: "Test Vault Co" })
    expect(screen.getByTestId("moc-crumb-platform").getAttribute("href")).toContain("/")
    const vertical = screen.getByTestId("moc-crumb-vertical")
    expect(vertical.getAttribute("href")).toContain("/maps/manufacturing")
    expect(vertical.textContent).toBe("Manufacturing")
    const current = screen.getByTestId("moc-crumb-current")
    expect(current.textContent).toBe("Test Vault Co")
    expect(current.tagName).toBe("SPAN")
  })

  it("an unregistered vertical slug falls back to the slug (never blank)", () => {
    renderCrumb({ vertical: "paving" })
    expect(screen.getByTestId("moc-crumb-current").textContent).toBe("paving")
  })
})
