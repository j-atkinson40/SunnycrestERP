/**
 * SchedulingKanbanCore — vitest unit tests. Phase B Session 4 Phase 4.2.
 *
 * Covers: Unassigned as leftmost lane, alphabetical driver ordering,
 * all drivers render (including empty), target-date resolution from
 * URL params, header includes day label + Finalize button.
 *
 * Drag drop mechanics aren't exercised here — jsdom doesn't emit
 * realistic pointer events and @dnd-kit relies on them. The handler
 * logic is unit-tested at the dispatch-service layer; full drag
 * verification is via Playwright + manual James walkthrough.
 */

import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"

import { FocusProvider } from "@/contexts/focus-context"
import type { FocusConfig } from "@/contexts/focus-registry"

import { SchedulingKanbanCore } from "./SchedulingKanbanCore"


// Mock dispatch-service — module is called synchronously at mount, so
// we vi.mock the whole module and provide stubs per-test.
vi.mock("@/services/dispatch-service", () => ({
  fetchTenantTime: vi.fn(),
  fetchSchedule: vi.fn(),
  fetchDeliveriesForRange: vi.fn(),
  fetchDrivers: vi.fn(),
  finalizeSchedule: vi.fn(),
  updateDelivery: vi.fn(),
}))


// Import the mocks so we can program per-test returns.
import {
  fetchDeliveriesForRange,
  fetchDrivers,
  fetchSchedule,
  fetchTenantTime,
} from "@/services/dispatch-service"


// Phase 4 Session 4 Intelligence prompt fetches (none here — pure UI).


const config: FocusConfig = {
  id: "funeral-scheduling",
  mode: "kanban",
  displayName: "Funeral Scheduling",
  coreComponent: SchedulingKanbanCore,
}


function Harness({
  initialUrl = "/dispatch/funeral-schedule?focus=funeral-scheduling",
  children,
}: {
  initialUrl?: string
  children: React.ReactNode
}) {
  return (
    <MemoryRouter initialEntries={[initialUrl]}>
      <FocusProvider>
        <TooltipProvider delay={0}>{children}</TooltipProvider>
      </FocusProvider>
    </MemoryRouter>
  )
}


describe("SchedulingKanbanCore — structure + data flow", () => {
  beforeEach(() => {
    vi.mocked(fetchTenantTime).mockResolvedValue({
      tenant_timezone: "America/New_York",
      local_iso: "2026-04-24T10:00:00-04:00",
      local_date: "2026-04-24",
      local_hour: 10,
      local_minute: 0,
    })
    vi.mocked(fetchSchedule).mockResolvedValue({
      id: "sch-1",
      company_id: "co-1",
      schedule_date: "2026-04-25",
      state: "draft",
      finalized_at: null,
      finalized_by_user_id: null,
      auto_finalized: false,
      last_reverted_at: null,
      last_revert_reason: null,
      created_at: null,
      updated_at: null,
    })
    vi.mocked(fetchDeliveriesForRange).mockResolvedValue([
      makeDelivery({
        id: "del-1",
        assigned_driver_id: "drv-dave",
        type_config: { family_name: "Smith", service_type: "graveside" },
      }),
      makeDelivery({
        id: "del-2",
        assigned_driver_id: null, // unassigned
        type_config: { family_name: "Jones", service_type: "graveside" },
      }),
    ])
    vi.mocked(fetchDrivers).mockResolvedValue([
      // Intentional reverse alphabetical to prove sort happens.
      {
        id: "drv-tom",
        license_number: "CDL-2",
        license_class: "CDL-A",
        active: true,
        display_name: "Tom Henderson",
      },
      {
        id: "drv-mike",
        license_number: "CDL-3",
        license_class: "CDL-B",
        active: true,
        display_name: "Mike Kowalski",
      },
      {
        id: "drv-dave",
        license_number: "CDL-1",
        license_class: "CDL-A",
        active: true,
        display_name: "Dave Miller",
      },
    ])
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it("defaults target date to tomorrow when no date param provided", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    // Tomorrow = 2026-04-25 (local_date 2026-04-24 + 1).
    await waitFor(() => {
      const core = document.querySelector('[data-slot="scheduling-focus-core"]')
      expect(core?.getAttribute("data-target-date")).toBe("2026-04-25")
    })
  })

  it("reads ?day= URL param as target date override", async () => {
    render(
      <Harness initialUrl="/dispatch/funeral-schedule?focus=funeral-scheduling&day=2026-04-28">
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      const core = document.querySelector('[data-slot="scheduling-focus-core"]')
      expect(core?.getAttribute("data-target-date")).toBe("2026-04-28")
    })
  })

  it("renders Unassigned as the leftmost lane (Phase 4.2 spec)", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    const lanes = await waitFor(() => {
      const nodes = document.querySelectorAll(
        '[data-slot="scheduling-focus-lane"]',
      )
      expect(nodes.length).toBeGreaterThan(0)
      return nodes
    })
    // First lane must be Unassigned.
    const first = lanes[0] as HTMLElement
    expect(first.getAttribute("data-unassigned")).toBe("true")
  })

  it("renders ALL drivers, even those with no deliveries (decide surface)", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      const lanes = document.querySelectorAll(
        '[data-slot="scheduling-focus-lane"]',
      )
      // Unassigned + 3 drivers = 4 lanes. Dave has one delivery;
      // Mike and Tom have zero but still appear.
      expect(lanes.length).toBe(4)
    })
    expect(screen.getByText("Dave Miller")).toBeInTheDocument()
    expect(screen.getByText("Mike Kowalski")).toBeInTheDocument()
    expect(screen.getByText("Tom Henderson")).toBeInTheDocument()
  })

  it("orders driver lanes alphabetically (Dave, Mike, Tom)", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    const lanes = await waitFor(() => {
      const nodes = document.querySelectorAll(
        '[data-slot="scheduling-focus-lane"]',
      )
      expect(nodes.length).toBe(4)
      return nodes
    })
    // Skip lane 0 (Unassigned) — check driver lanes in order.
    const laneKeys = Array.from(lanes).map((n) =>
      (n as HTMLElement).getAttribute("data-lane") ?? "",
    )
    // Driver lanes end with the driver id; alphabetical by display
    // name → Dave, Mike, Tom → drv-dave, drv-mike, drv-tom.
    expect(laneKeys[1]).toMatch(/:drv-dave$/)
    expect(laneKeys[2]).toMatch(/:drv-mike$/)
    expect(laneKeys[3]).toMatch(/:drv-tom$/)
  })

  it("empty driver lane shows a dashed drop-here placeholder", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      const empty = document.querySelectorAll(
        '[data-slot="scheduling-focus-lane-empty"]',
      )
      // Unassigned has 1 delivery; Dave has 1; Mike/Tom are empty = 2.
      expect(empty.length).toBe(2)
    })
  })

  it("header shows day label + Change day selector + Finalize button", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      expect(screen.getByText(/Tomorrow,/)).toBeInTheDocument()
    })
    expect(
      document.querySelector('[data-slot="scheduling-focus-day-selector"]'),
    ).toBeInTheDocument()
    const finalize = document.querySelector(
      '[data-slot="scheduling-focus-finalize"]',
    ) as HTMLElement
    expect(finalize).toBeInTheDocument()
    expect(finalize.textContent).toMatch(/Finalize Tomorrow/)
    const close = document.querySelector(
      '[data-slot="scheduling-focus-close"]',
    )
    expect(close).toBeInTheDocument()
  })

  it("finalized schedule hides the Finalize button + shows attribution hint", async () => {
    vi.mocked(fetchSchedule).mockResolvedValue({
      id: "sch-2",
      company_id: "co-1",
      schedule_date: "2026-04-25",
      state: "finalized",
      finalized_at: "2026-04-24T13:00:00Z",
      finalized_by_user_id: "user-admin",
      auto_finalized: false,
      last_reverted_at: null,
      last_revert_reason: null,
      created_at: null,
      updated_at: null,
    })
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      expect(screen.getByText(/revert to draft/i)).toBeInTheDocument()
    })
    // Finalize button absent when state=finalized.
    expect(
      document.querySelector('[data-slot="scheduling-focus-finalize"]'),
    ).toBeNull()
  })
})


// ── Fixture ─────────────────────────────────────────────────────────


function makeDelivery(
  overrides: Partial<
    import("@/services/dispatch-service").DeliveryDTO
  > = {},
): import("@/services/dispatch-service").DeliveryDTO {
  return {
    id: "del-default",
    company_id: "co-1",
    order_id: "so-1",
    customer_id: null,
    delivery_type: "vault",
    status: "scheduled",
    priority: "normal",
    requested_date: "2026-04-25",
    scheduled_at: null,
    completed_at: null,
    scheduling_type: "kanban",
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    assigned_driver_id: null,
    hole_dug_status: "unknown",
    type_config: {
      family_name: "Test",
      service_type: "graveside",
    },
    special_instructions: null,
    ...overrides,
  }
}
