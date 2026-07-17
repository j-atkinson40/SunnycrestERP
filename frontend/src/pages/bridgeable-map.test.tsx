/**
 * The Bridgeable Map page — sections-with-cards (The Sunnycrest Workshop;
 * the P3 pager retired by the operator's call — sections ARE the overflow
 * management now). Page-level pins: the sections render from the merged
 * read, every task gets a card (no pagination truncation), the admin add
 * affordance mounts, the room stays.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import BridgeableMapPage from "./bridgeable-map"
import * as svc from "@/services/moc-map-service"
import type { MapTask } from "@/services/moc-map-service"

vi.mock("@/contexts/auth-context", () => ({
  useAuth: () => ({ company: { name: "Test Vault Co" }, isAdmin: true }),
}))

vi.mock("@/services/moc-map-service", async () => {
  const actual = await vi.importActual<typeof svc>("@/services/moc-map-service")
  return { ...actual, getMapTasks: vi.fn(), forkTask: vi.fn() }
})

function task(i: number, type: string | null = null): MapTask {
  return {
    id: `t-${i}`, name: `Task ${String(i).padStart(2, "0")}`,
    display_order: i, scope: "vertical_default", triggers: [],
    task_type: type,
    workflow: { exists: true, available: true, label: "WF" },
  } as MapTask
}

const TASKS = [
  ...Array.from({ length: 20 }, (_, i) => task(i + 1)),
  ...Array.from({ length: 3 }, (_, i) => task(100 + i, "accounting")),
]

function mount() {
  return render(<MemoryRouter><BridgeableMapPage /></MemoryRouter>)
}

describe("BridgeableMapPage sections", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.mocked(svc.getMapTasks).mockResolvedValue({
      vertical: "manufacturing", tasks: structuredClone(TASKS),
    })
  })

  it("renders derived sections with EVERY task carded — no pager, no truncation", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-sections"))
    // The 23-task stress case lays out whole: 20 untyped under General,
    // 3 typed under accounting. The pager is gone.
    expect(screen.getAllByTestId(/^map-card-t-/)).toHaveLength(23)
    expect(screen.getByTestId("map-section-accounting")).toBeInTheDocument()
    expect(screen.getByTestId("map-section-General")).toBeInTheDocument()
    expect(screen.queryByTestId("map-pager")).toBeNull()
  })

  it("mounts the admin add affordances (general + per-section)", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-sections"))
    expect(screen.getByTestId("map-add-task-button")).toBeInTheDocument()
    expect(screen.getByTestId("map-section-add-accounting")).toBeInTheDocument()
  })

  it("keeps the room — the coming sections read as room, not shrug", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-sections"))
    expect(screen.getByTestId("map-room")).toBeInTheDocument()
  })
})
