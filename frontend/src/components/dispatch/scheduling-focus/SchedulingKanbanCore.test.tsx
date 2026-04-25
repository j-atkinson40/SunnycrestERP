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
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { MemoryRouter } from "react-router-dom"
import { TooltipProvider } from "@/components/ui/tooltip"

import { FocusProvider } from "@/contexts/focus-context"
import type { FocusConfig } from "@/contexts/focus-registry"
import { FocusDndProvider } from "@/components/focus/FocusDndProvider"

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
  // Phase B Session 4.4.3 — DateBox components in the header call
  // useDaySummary which calls fetchDaySummary. The flanking date
  // boxes resolve to centerDate ± 1, so each render fires one
  // request per box; tests don't care about resolved values for
  // the structural assertions, so a stable empty-zero summary
  // satisfies every case.
  fetchDaySummary: vi.fn(),
}))


// Import the mocks so we can program per-test returns.
import {
  fetchDaySummary,
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
  // Phase 4.3b D-1 elevation. SchedulingKanbanCore subscribes to
  // the elevated DndContext via `useDndMonitor`; the provider must
  // be a parent or the hook throws. Production wires this via
  // Focus.tsx → FocusDndProvider; tests mount the provider
  // directly. TooltipProvider stays inside so tooltip portals can
  // resolve.
  return (
    <MemoryRouter initialEntries={[initialUrl]}>
      <FocusProvider>
        <FocusDndProvider>
          <TooltipProvider delay={0}>{children}</TooltipProvider>
        </FocusDndProvider>
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
        // Phase 4.3.2 (r56) — delivery.primary_assignee_id is a
        // users.id; fixtures use the same string for driver.user_id
        // below for grouping-match.
        primary_assignee_id: "drv-dave",
        type_config: { family_name: "Smith", service_type: "graveside" },
      }),
      makeDelivery({
        id: "del-2",
        primary_assignee_id: null, // unassigned
        type_config: { family_name: "Jones", service_type: "graveside" },
      }),
    ])
    vi.mocked(fetchDrivers).mockResolvedValue([
      // Intentional reverse alphabetical to prove sort happens.
      // user_id == id for fixture simplicity — real backend would
      // separate drivers.id from drivers.employee_id (users.id).
      {
        id: "drv-tom",
        user_id: "drv-tom",
        license_number: "CDL-2",
        license_class: "CDL-A",
        active: true,
        display_name: "Tom Henderson",
      },
      {
        id: "drv-mike",
        user_id: "drv-mike",
        license_number: "CDL-3",
        license_class: "CDL-B",
        active: true,
        display_name: "Mike Kowalski",
      },
      {
        id: "drv-dave",
        user_id: "drv-dave",
        license_number: "CDL-1",
        license_class: "CDL-A",
        active: true,
        display_name: "Dave Miller",
      },
    ])
    // Phase 4.4.3 default: empty draft summary on every date the
    // flanking DateBoxes ask about. Per-test cases override.
    vi.mocked(fetchDaySummary).mockImplementation(async (dateStr: string) => ({
      date: dateStr,
      total_deliveries: 0,
      unassigned_count: 0,
      finalize_status: "draft" as const,
      finalized_at: null,
    }))
  })

  afterEach(async () => {
    vi.clearAllMocks()
    // Phase 4.4.3 — module-scoped cache in useDaySummary persists
    // across tests within the same vitest worker. Clear it between
    // tests so per-test mockResolvedValue(...) fixtures don't get
    // shadowed by a cached prior summary.
    const { _resetDaySummaryCache } = await import("@/hooks/useDaySummary")
    _resetDaySummaryCache()
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

  it("header shows day label + day selector + Finalize button (Close removed in Aesthetic Arc Session 1)", async () => {
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
    // Aesthetic Arc Session 1 — Close button retired per Section 0
    // Restraint Translation Principle. Backdrop click + Esc already
    // dismiss; the explicit button was decorative. Operator-respect
    // says trust the user with platform conventions. This assertion
    // is a regression guard against accidental re-add.
    const close = document.querySelector(
      '[data-slot="scheduling-focus-close"]',
    )
    expect(close).toBeNull()
  })

  it("each rendered card is wrapped in a card-slot with data-ghost='false' at rest (Phase 4.2.2)", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    // Phase 4.2.2 — every in-lane card now sits in a
    // `scheduling-focus-card-slot` wrapper. At rest, the wrapper
    // carries `data-ghost="false"` (no card is being dragged). When
    // drag starts, the slot whose id matches `activeDeliveryId`
    // flips to `data-ghost="true"` + `opacity-40 pointer-events-none`
    // to hint "came from here" while DragOverlay owns the floating
    // preview. Full drag simulation isn't exercised in jsdom (dnd-kit
    // needs real pointer events); this is the DOM-contract check.
    const slots = await waitFor(() => {
      const nodes = document.querySelectorAll(
        '[data-slot="scheduling-focus-card-slot"]',
      )
      expect(nodes.length).toBeGreaterThan(0)
      return nodes
    })
    for (const slot of Array.from(slots)) {
      expect(slot.getAttribute("data-ghost")).toBe("false")
    }
  })

  it("DragOverlay container is mounted while DndContext is active (Phase 4.2.2)", async () => {
    // @dnd-kit renders <DragOverlay> into a portal on dragStart; at
    // rest there's no floating preview in the DOM. What we CAN assert
    // is that the DndContext wrapping our kanban renders — meaning
    // the body is the post-loading render path (not the error state
    // or the loading skeleton). Structural guard against accidental
    // DndContext removal.
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      expect(
        document.querySelector('[data-slot="scheduling-focus-kanban"]'),
      ).toBeInTheDocument()
    })
    // drag-preview slot is NOT present at rest (no active drag).
    expect(
      document.querySelector('[data-slot="scheduling-focus-drag-preview"]'),
    ).toBeNull()
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

  // Phase B Session 4.4.3 — date-box flanking affordance.

  it("renders two flanking DateBoxes around the H2 day label", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    const boxes = await waitFor(() => {
      const nodes = document.querySelectorAll(
        '[data-slot="scheduling-focus-date-box"]',
      )
      expect(nodes.length).toBe(2)
      return nodes
    })
    // Center date is tomorrow (2026-04-25). Flanking dates are
    // 2026-04-24 (today / day-before) and 2026-04-26 (day-after).
    const dates = Array.from(boxes).map((b) => b.getAttribute("data-date"))
    expect(dates).toContain("2026-04-24")
    expect(dates).toContain("2026-04-26")
  })

  it("DateBoxes start in the inactive (data-active='false') state", async () => {
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    const boxes = await waitFor(() => {
      const nodes = document.querySelectorAll(
        '[data-slot="scheduling-focus-date-box"]',
      )
      expect(nodes.length).toBe(2)
      return nodes
    })
    for (const box of Array.from(boxes)) {
      expect(box.getAttribute("data-active")).toBe("false")
      expect(box.getAttribute("aria-pressed")).toBe("false")
    }
  })

  it("clicking a DateBox toggles its active state on, then off", async () => {
    const user = userEvent.setup()
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    const today = await waitFor(() => {
      const node = document.querySelector(
        '[data-slot="scheduling-focus-date-box"][data-date="2026-04-24"]',
      ) as HTMLElement | null
      expect(node).not.toBeNull()
      return node!
    })
    expect(today.getAttribute("data-active")).toBe("false")

    await user.click(today)
    expect(today.getAttribute("data-active")).toBe("true")
    expect(today.getAttribute("aria-pressed")).toBe("true")

    // Click again — toggle off.
    await user.click(today)
    expect(today.getAttribute("data-active")).toBe("false")
    expect(today.getAttribute("aria-pressed")).toBe("false")
  })

  it("date boxes toggle independently (both can be active simultaneously)", async () => {
    const user = userEvent.setup()
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      const nodes = document.querySelectorAll(
        '[data-slot="scheduling-focus-date-box"]',
      )
      expect(nodes.length).toBe(2)
    })
    const prev = document.querySelector(
      '[data-slot="scheduling-focus-date-box"][data-date="2026-04-24"]',
    ) as HTMLElement
    const next = document.querySelector(
      '[data-slot="scheduling-focus-date-box"][data-date="2026-04-26"]',
    ) as HTMLElement

    await user.click(prev)
    await user.click(next)
    expect(prev.getAttribute("data-active")).toBe("true")
    expect(next.getAttribute("data-active")).toBe("true")
  })

  it("H2 click still opens the day-jump popover (regression)", async () => {
    const user = userEvent.setup()
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    const trigger = await waitFor(() => {
      const node = document.querySelector(
        '[data-slot="scheduling-focus-day-selector"]',
      ) as HTMLElement | null
      expect(node).not.toBeNull()
      return node!
    })
    // Popover menu is absent at rest.
    expect(
      document.querySelector(
        '[data-slot="scheduling-focus-day-selector-menu"]',
      ),
    ).toBeNull()
    await user.click(trigger)
    // Menu appears after click — the H2 IS the trigger now (no
    // separate "Change day" sub-button).
    expect(
      document.querySelector(
        '[data-slot="scheduling-focus-day-selector-menu"]',
      ),
    ).toBeInTheDocument()
  })

  it("any-day jump via popover resets date-box active flags", async () => {
    const user = userEvent.setup()
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    // Engage one box.
    const prev = await waitFor(() => {
      const node = document.querySelector(
        '[data-slot="scheduling-focus-date-box"][data-date="2026-04-24"]',
      ) as HTMLElement | null
      expect(node).not.toBeNull()
      return node!
    })
    await user.click(prev)
    expect(prev.getAttribute("data-active")).toBe("true")

    // Open the day-jump popover and pick a different day.
    const trigger = document.querySelector(
      '[data-slot="scheduling-focus-day-selector"]',
    ) as HTMLElement
    await user.click(trigger)
    // Pick "+3" — fourth option in the listbox (Today, Tomorrow,
    // +2, +3, ...). Use role=option to find clickable items.
    const options = document.querySelectorAll('[role="option"]')
    expect(options.length).toBeGreaterThan(3)
    await user.click(options[3] as HTMLElement)

    // After day jump, the new flanking boxes appear at the new
    // center; their active state should be reset to false.
    await waitFor(() => {
      const boxes = document.querySelectorAll(
        '[data-slot="scheduling-focus-date-box"]',
      )
      expect(boxes.length).toBe(2)
      for (const box of Array.from(boxes)) {
        expect(box.getAttribute("data-active")).toBe("false")
      }
    })
  })

  it("DateBox surface uses bg-surface-elevated (calibration regression)", async () => {
    // Aesthetic-coherence regression — DateBox must NOT drift to
    // generic SaaS chip register (bg-muted, rounded-full, neutral
    // border). Calibrated against AncillaryPoolPin + DeliveryCard:
    // bg-surface-elevated + border-border-subtle + radius-sm. If
    // a future refactor flips these tokens (e.g. someone rounds-
    // everything to rounded-full or swaps surface-elevated for
    // muted), this test catches it before merge.
    render(
      <Harness>
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    const box = await waitFor(() => {
      const node = document.querySelector(
        '[data-slot="scheduling-focus-date-box"]',
      ) as HTMLElement | null
      expect(node).not.toBeNull()
      return node!
    })
    const cls = box.className
    expect(cls).toMatch(/bg-surface-elevated/)
    expect(cls).toMatch(/border-border-subtle/)
    expect(cls).toMatch(/rounded-sm/)
    // Drift guards — these tokens MUST NOT appear at rest.
    expect(cls).not.toMatch(/bg-muted\b/)
    expect(cls).not.toMatch(/rounded-full/)
    expect(cls).not.toMatch(/shadow-md/)
  })
})


// ── Phase 4.3.3.1 — attached-ancillary parity with Monitor ──────────


describe("SchedulingKanbanCore — attached-ancillary parity (Phase 4.3.3.1)", () => {
  beforeEach(() => {
    vi.mocked(fetchTenantTime).mockResolvedValue({
      tenant_timezone: "America/New_York",
      local_iso: "2026-04-25T10:00:00-04:00",
      local_date: "2026-04-25",
      local_hour: 10,
      local_minute: 0,
    })
    vi.mocked(fetchSchedule).mockResolvedValue({
      id: "sch-3",
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
    vi.mocked(fetchDrivers).mockResolvedValue([
      {
        id: "drv-bob",
        user_id: "drv-bob",
        license_number: "CDL-4",
        license_class: "CDL-A",
        active: true,
        display_name: "Bob Johnson",
      },
    ])
    // Bob has Murphy primary + a Murphy urn-rider ancillary attached
    // to it (mirrors the dispatch demo seed's attached-state row).
    vi.mocked(fetchDeliveriesForRange).mockResolvedValue([
      makeDelivery({
        id: "murphy-primary",
        primary_assignee_id: "drv-bob",
        type_config: {
          family_name: "Murphy",
          service_type: "graveside",
        },
      }),
      makeDelivery({
        id: "murphy-rider",
        scheduling_type: "ancillary",
        attached_to_delivery_id: "murphy-primary",
        primary_assignee_id: "drv-bob",
        type_config: {
          family_name: "Murphy",
          service_type: "ancillary_pickup",
          vault_type: "Urn vault (rider)",
        },
      }),
    ])
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it("renders +N ancillary badge on parent in Focus (mirrors Monitor)", async () => {
    render(
      <Harness initialUrl="/?day=2026-04-25">
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      expect(
        document.querySelector('[data-slot="scheduling-focus-kanban"]'),
      ).toBeInTheDocument()
    })
    // Parent card should carry an ancillary badge with count=1.
    const badges = document.querySelectorAll(
      '[data-slot="dispatch-ancillary-badge"]',
    )
    expect(badges.length).toBe(1)
    const countChip = badges[0].querySelector(
      '[data-slot="dispatch-ancillary-badge-count"]',
    )
    expect(countChip?.textContent).toBe("1")
  })

  it("attached ancillary does NOT render as a standalone card", async () => {
    render(
      <Harness initialUrl="/?day=2026-04-25">
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      expect(
        document.querySelector('[data-slot="scheduling-focus-kanban"]'),
      ).toBeInTheDocument()
    })
    // 1 primary delivery card + 0 standalone ancillary cards.
    expect(
      document.querySelectorAll('[data-slot="dispatch-delivery-card"]').length,
    ).toBe(1)
    expect(
      document.querySelectorAll('[data-slot="dispatch-ancillary-card"]').length,
    ).toBe(0)
  })

  it("clicking the badge expands inline drawer with attached ancillary", async () => {
    const user = userEvent.setup()
    render(
      <Harness initialUrl="/?day=2026-04-25">
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      expect(
        document.querySelector('[data-slot="scheduling-focus-kanban"]'),
      ).toBeInTheDocument()
    })
    // Drawer absent at rest.
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-expanded"]'),
    ).toBeNull()
    const badge = document.querySelector(
      '[data-slot="dispatch-ancillary-badge"]',
    ) as HTMLElement
    await user.click(badge)
    // Drawer appears + contains the attached ancillary item.
    const drawer = document.querySelector(
      '[data-slot="dispatch-ancillary-expanded"]',
    )
    expect(drawer).toBeInTheDocument()
    const items = drawer?.querySelectorAll(
      '[data-slot="dispatch-ancillary-expanded-item"]',
    )
    expect(items?.length).toBe(1)
    expect(items?.[0].getAttribute("data-ancillary-id")).toBe("murphy-rider")
    // Click the badge again → collapse.
    await user.click(badge)
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-expanded"]'),
    ).toBeNull()
  })

  // Phase 4.3b.4 — drawer items are drag sources.
  //
  // Each expanded drawer item now wraps useDraggable so the
  // dispatcher can drag the rider out to detach. Click still opens
  // QuickEdit because PointerSensor activation constraint
  // (distance: 8 from FocusDndProvider) cleanly separates click
  // from drag. This test verifies the structural wiring: items
  // render with the canonical drag attributes; data-slot +
  // data-ancillary-id (Phase 4.3.3.1 pre-positioned) preserved.
  it("drawer items are draggable (Phase 4.3b.4 detach gesture)", async () => {
    const user = userEvent.setup()
    render(
      <Harness initialUrl="/?day=2026-04-25">
        <SchedulingKanbanCore focusId="funeral-scheduling" config={config} />
      </Harness>,
    )
    await waitFor(() => {
      expect(
        document.querySelector('[data-slot="scheduling-focus-kanban"]'),
      ).toBeInTheDocument()
    })
    const badge = document.querySelector(
      '[data-slot="dispatch-ancillary-badge"]',
    ) as HTMLElement
    await user.click(badge)
    const drawerItem = document.querySelector(
      '[data-slot="dispatch-ancillary-expanded-item"]',
    ) as HTMLElement
    expect(drawerItem).toBeTruthy()
    // Whole-element drag per Phase 4.3b.3.2 platform principle —
    // useDraggable listeners are on the button itself, no separate
    // grip handle.
    expect(drawerItem.getAttribute("aria-roledescription")).toBe("draggable")
    expect(drawerItem.tagName).toBe("BUTTON")
    // Phase 4.3.3.1 pre-positioned data attributes survive the
    // 4.3b.4 useDraggable wrap.
    expect(drawerItem.getAttribute("data-ancillary-id")).toBe("murphy-rider")
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
    primary_assignee_id: null,
    helper_user_id: null,
    attached_to_delivery_id: null,
    driver_start_time: null,
    helper_user_name: null,
    attached_to_family_name: null,
    hole_dug_status: "unknown",
    type_config: {
      family_name: "Test",
      service_type: "graveside",
    },
    special_instructions: null,
    ...overrides,
  }
}
