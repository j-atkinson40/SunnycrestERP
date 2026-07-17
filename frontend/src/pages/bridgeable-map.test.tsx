/**
 * The Bridgeable Map HOME — the three-part composition's pins (The Map
 * Home campaign).
 *
 *  * THE STABLE SPINE — area cards derived from types-with-content, order
 *    a pure function of the names (alphabetical, General last): shuffled
 *    input, same spine — PERSONALIZATION NEVER REORDERS IT (the
 *    navigation guarantee, pinned).
 *  * THE YOURS SECTION — forks + additions gathered, area-linked.
 *  * THE ROOM — stays.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import BridgeableMapPage, { deriveAreaSummaries } from "./bridgeable-map"
import * as svc from "@/services/moc-map-service"
import type { MapTask } from "@/services/moc-map-service"

vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ company: { name: "Test Vault Co" }, isAdmin: true }),
}))

vi.mock("@/services/moc-map-service", async () => {
  const actual = await vi.importActual<typeof svc>("@/services/moc-map-service")
  return {
    ...actual,
    getMapTasks: vi.fn(),
    forkTask: vi.fn(),
    getSuggestions: vi.fn().mockResolvedValue([]),
    recordEngagement: vi.fn(),
  }
})

function task(i: number, type: string | null, scope = "vertical_default"): MapTask {
  return {
    id: `t-${i}`, name: `Task ${i}`, display_order: i,
    scope: scope as MapTask["scope"], triggers: [], task_type: type,
    workflow: { exists: true, available: true, label: "WF" },
  } as MapTask
}

describe("deriveAreaSummaries — the stable spine", () => {
  it("order is a pure function of the names — shuffled input, same spine", () => {
    const a = deriveAreaSummaries([
      task(1, "Operations"), task(2, "Accounting"), task(3, null),
    ])
    const b = deriveAreaSummaries([
      task(3, null), task(1, "Operations"), task(2, "Accounting"),
    ])
    expect(a.map((x) => x.area)).toEqual(["Accounting", "Operations", "General"])
    expect(b.map((x) => x.area)).toEqual(a.map((x) => x.area))
  })

  it("counts tasks + the live fleet honestly", () => {
    const out = deriveAreaSummaries([
      { ...task(1, "Accounting"), triggers: [{ id: "x", kind: "schedule", config: {}, display_order: 0, is_live: true, is_active: true } as never] },
      task(2, "Accounting"),
    ])
    expect(out[0]).toEqual({ area: "Accounting", taskCount: 2, liveCount: 1 })
  })
})

describe("BridgeableMapPage — the three-part home", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.mocked(svc.getSuggestions).mockResolvedValue([])
    vi.mocked(svc.getMapTasks).mockResolvedValue({
      vertical: "manufacturing",
      tasks: [
        task(1, "Accounting"),
        task(2, "Accounting"),
        task(3, "Operations"),
        task(4, "Accounting", "tenant_override"),
      ],
    })
  })

  function mount() {
    return render(<MemoryRouter><BridgeableMapPage /></MemoryRouter>)
  }

  it("renders the spine (area cards) + yours + the room", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-area-spine"))
    expect(screen.getByTestId("map-area-Accounting")).toBeInTheDocument()
    expect(screen.getByTestId("map-area-Operations")).toBeInTheDocument()
    expect(screen.getByTestId("map-area-count-Accounting").textContent)
      .toContain("3 tasks")
    // YOURS — the fork gathered, linked into its area.
    expect(screen.getByTestId("map-yours-section")).toBeInTheDocument()
    expect(screen.getByTestId("map-card-area-link-t-4").getAttribute("href"))
      .toBe("/bridgeable-map/Accounting")
    expect(screen.getByTestId("map-room")).toBeInTheDocument()
  })

  it("the rail's absence leaves the home whole (empty-honest)", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-area-spine"))
    expect(screen.queryByTestId("map-suggestions-rail")).toBeNull()
  })
})
