/**
 * MoCHome (Phase 1.2 two-pane).
 *
 * The home is two-pane: the Verticals rail (verticals-list behavior is
 * covered by MoCVerticalsRail.test) BESIDE a content overview. These assert
 * the two-pane structure + the 1.2 contrast fix (the §18 surface island that
 * makes content legible against the admin shell in both modes).
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import MoCHome from "./MoCHome"

// The rail self-fetches; stub it so the home renders without a live call.
vi.mock("@/bridgeable-admin/services/moc-service", () => ({
  listPages: vi.fn().mockResolvedValue([]),
}))

afterEach(() => vi.clearAllMocks())

function renderHome() {
  return render(
    <MemoryRouter>
      <MoCHome />
    </MemoryRouter>,
  )
}

describe("MoCHome two-pane", () => {
  it("renders the two-pane: the Verticals rail beside a content area", async () => {
    renderHome()
    expect(await screen.findByTestId("moc-verticals-rail")).toBeInTheDocument()
    expect(screen.getByTestId("moc-home-content")).toBeInTheDocument()
  })

  it("applies the §18 surface (contrast fix) on the home root, not a bare/transparent container", () => {
    renderHome()
    const root = screen.getByTestId("moc-home")
    // The fix: §18 surface-base behind the content so §18 content tones render
    // legibly against the admin shell in both modes (was: transparent → text
    // fell onto the slate-50 admin bg → dark-mode washout).
    expect(root.className).toContain("bg-surface-base")
  })

  it("the content area is the overview/select prompt (no vertical selected at '/')", () => {
    renderHome()
    expect(screen.getByText("Maps of Content")).toBeInTheDocument()
    expect(screen.getByText("Select a vertical")).toBeInTheDocument()
  })
})
