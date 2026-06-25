/**
 * MoCVerticalsRail (Phase 1.2 two-pane).
 *
 * The rail = the verticals nav: seeded → live link to /maps/:vertical;
 * unseeded → §18 "no map yet" non-link (the 1.1 not-built truth); the
 * route's :vertical is highlighted active (aria-current).
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"

import { MoCVerticalsRail } from "./MoCVerticalsRail"

vi.mock("@/bridgeable-admin/services/moc-service", () => ({
  listPages: vi.fn(),
}))
import { listPages } from "@/bridgeable-admin/services/moc-service"

const mfgPage = {
  id: "mp1",
  scope: "vertical_default" as const,
  vertical: "manufacturing",
  tenant_id: null,
  slug: "manufacturing-map",
  title: "Manufacturing",
  description: null,
  sections: [],
}

afterEach(() => vi.clearAllMocks())

function renderRail(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<MoCVerticalsRail />} />
        <Route path="/maps/:vertical" element={<MoCVerticalsRail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe("MoCVerticalsRail", () => {
  it("seeded vertical is a live link; the rest are §18 'no map yet' non-links", async () => {
    ;(listPages as ReturnType<typeof vi.fn>).mockResolvedValue([mfgPage])
    renderRail("/")

    const mfg = await screen.findByRole("link", { name: "Manufacturing" })
    expect(mfg.getAttribute("href")).toContain("/maps/manufacturing")

    for (const label of ["Funeral Home", "Cemetery", "Crematory"]) {
      expect(screen.getByText(label)).toBeInTheDocument()
      expect(screen.queryByRole("link", { name: label })).not.toBeInTheDocument()
    }
    expect(screen.getAllByText(/no map yet/i)).toHaveLength(3)
    expect(screen.queryByText(/no longer available/i)).not.toBeInTheDocument()
  })

  it("highlights the route's vertical as active (aria-current)", async () => {
    ;(listPages as ReturnType<typeof vi.fn>).mockResolvedValue([mfgPage])
    renderRail("/maps/manufacturing")

    const mfg = await screen.findByRole("link", { name: "Manufacturing" })
    expect(mfg).toHaveAttribute("aria-current", "page")
  })

  it("on the home (no :vertical), nothing is active", async () => {
    ;(listPages as ReturnType<typeof vi.fn>).mockResolvedValue([mfgPage])
    renderRail("/")
    const mfg = await screen.findByRole("link", { name: "Manufacturing" })
    expect(mfg).not.toHaveAttribute("aria-current")
  })

  it("degrades to all-not-yet if the list fetch fails (no crash, no links)", async () => {
    ;(listPages as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("boom"))
    renderRail("/")
    await waitFor(() =>
      expect(screen.getAllByText(/no map yet/i).length).toBeGreaterThanOrEqual(4),
    )
    expect(screen.queryByRole("link")).not.toBeInTheDocument()
  })
})
