/**
 * The Bridgeable Map's task pager — 10 per page, chevrons underneath,
 * clamped + reset on tab switch; hidden when one page suffices.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
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

describe("BridgeableMapPage pager", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(svc.getMapTasks).mockResolvedValue({
      vertical: "manufacturing", tasks: structuredClone(TASKS),
    })
  })

  it("shows 10 tasks per page with the count label", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-pager"))
    expect(screen.getAllByTestId(/^map-task-t-/)).toHaveLength(10)
    expect(screen.getByTestId("map-pager-label").textContent)
      .toContain("Page 1 of 3")
    expect(screen.getByTestId("map-pager-label").textContent).toContain("23 tasks")
    expect(screen.getByTestId("map-pager-prev")).toBeDisabled()
  })

  it("chevrons page through; the last page holds the remainder", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-pager"))
    fireEvent.click(screen.getByTestId("map-pager-next"))
    expect(screen.getByTestId("map-pager-label").textContent).toContain("Page 2 of 3")
    expect(screen.getByTestId("map-task-t-11")).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("map-pager-next"))
    expect(screen.getAllByTestId(/^map-task-t-/)).toHaveLength(3)
    expect(screen.getByTestId("map-pager-next")).toBeDisabled()
  })

  it("switching a group tab resets to page 1 and hides a needless pager", async () => {
    mount()
    await waitFor(() => screen.getByTestId("map-pager"))
    fireEvent.click(screen.getByTestId("map-pager-next"))
    fireEvent.click(screen.getByTestId("map-group-accounting"))
    // 3 accounting tasks → one page → the pager disappears entirely.
    expect(screen.queryByTestId("map-pager")).toBeNull()
    expect(screen.getAllByTestId(/^map-task-t-/)).toHaveLength(3)
  })
})
