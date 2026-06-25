/**
 * MoCHome vertical-list states (MoC Phase 1.1).
 *
 * The front door must render ALL four verticals honestly: a seeded one as a
 * LIVE link to its map; an unseeded one in the §18 "no map yet" state (muted,
 * non-link) — the UNBUILT truth, distinct from the orphan "no longer
 * available" wording. These tests pin that distinction.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import MoCHome from "./MoCHome"

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

function renderHome() {
  return render(
    <MemoryRouter>
      <MoCHome />
    </MemoryRouter>,
  )
}

describe("MoCHome vertical list", () => {
  it("renders the seeded vertical as a LIVE link and the rest as 'no map yet'", async () => {
    ;(listPages as ReturnType<typeof vi.fn>).mockResolvedValue([mfgPage])
    renderHome()

    // Manufacturing — a real link into its map.
    const mfgLink = await screen.findByRole("link", { name: "Manufacturing" })
    expect(mfgLink.getAttribute("href")).toContain("/maps/manufacturing")

    // The three unseeded verticals — present, in the not-yet state, NOT links.
    for (const label of ["Funeral Home", "Cemetery", "Crematory"]) {
      expect(screen.getByText(label)).toBeInTheDocument()
      expect(
        screen.queryByRole("link", { name: label }),
      ).not.toBeInTheDocument()
    }

    // The not-yet caption is the UNBUILT truth — never the orphan wording.
    const notYet = screen.getAllByText(/no map yet/i)
    expect(notYet).toHaveLength(3)
    expect(screen.queryByText(/no longer available/i)).not.toBeInTheDocument()
  })

  it("with nothing seeded, all four verticals show 'no map yet' (no live links, no orphan wording)", async () => {
    ;(listPages as ReturnType<typeof vi.fn>).mockResolvedValue([])
    renderHome()

    await waitFor(() =>
      expect(screen.getAllByText(/no map yet/i)).toHaveLength(4),
    )
    for (const label of ["Manufacturing", "Funeral Home", "Cemetery", "Crematory"]) {
      expect(screen.getByText(label)).toBeInTheDocument()
      expect(
        screen.queryByRole("link", { name: label }),
      ).not.toBeInTheDocument()
    }
    expect(screen.queryByText(/no longer available/i)).not.toBeInTheDocument()
  })
})
