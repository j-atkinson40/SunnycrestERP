/**
 * MonitorDayColumn — vitest unit tests. Phase B Session 1 Phase 3.1+3.2.
 *
 * Covers: header state rendering (draft/finalized/not_created),
 * Finalize button style-parity with finalized attribution (same
 * typography, color differentiates), horizontal driver-lane kanban
 * layout, unassigned-lane surfacing, empty-state placeholder,
 * ancillary inline expand.
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { DndContext } from "@dnd-kit/core"
import { TooltipProvider } from "@/components/ui/tooltip"

import type {
  DeliveryDTO,
  DriverDTO,
  ScheduleStateDTO,
} from "@/services/dispatch-service"

import { MonitorDayColumn } from "./MonitorDayColumn"


function makeDelivery(overrides: Partial<DeliveryDTO> = {}): DeliveryDTO {
  return {
    id: "del-" + Math.random().toString(36).slice(2, 8),
    company_id: "co-1",
    order_id: null,
    customer_id: null,
    delivery_type: "vault",
    status: "scheduled",
    priority: "normal",
    requested_date: "2026-04-24",
    scheduled_at: null,
    completed_at: null,
    scheduling_type: "kanban",
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    assigned_driver_id: null,
    hole_dug_status: "unknown",
    type_config: { family_name: "Smith", service_type: "graveside" },
    special_instructions: null,
    ...overrides,
  }
}


function makeSchedule(overrides: Partial<ScheduleStateDTO> = {}): ScheduleStateDTO {
  return {
    id: "sch-1",
    company_id: "co-1",
    schedule_date: "2026-04-24",
    state: "draft",
    finalized_at: null,
    finalized_by_user_id: null,
    auto_finalized: false,
    last_reverted_at: null,
    last_revert_reason: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}


const drivers: DriverDTO[] = [
  { id: "driver-1", license_number: "CDL-1", license_class: "CDL-A", active: true, display_name: "Dave Miller" },
  { id: "driver-2", license_number: "CDL-2", license_class: "CDL-A", active: true, display_name: "Tom Henderson" },
]


const defaultProps = {
  dateStr: "2026-04-24",
  dayLabel: "Tomorrow",
  drivers,
  ancillaryCounts: new Map<string, number>(),
  ancillariesByParent: new Map<string, DeliveryDTO[]>(),
  onOpenEdit: () => {},
  onCycleHoleDug: () => {},
  onFinalize: () => {},
  onOpenScheduling: () => {},
}


function Harness({ children }: { children: React.ReactNode }) {
  return (
    <TooltipProvider delay={0}>
      <DndContext>{children}</DndContext>
    </TooltipProvider>
  )
}


describe("MonitorDayColumn — header rendering", () => {
  it("draft schedule shows DRAFT badge + Finalize affordance in attribution slot", () => {
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule({ state: "draft" })}
          deliveries={[makeDelivery()]}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-day-draft-badge"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="dispatch-day-finalize-btn"]'),
    ).toBeInTheDocument()
  })

  it("Finalize control sits in the same slot as finalized attribution (Phase 3.1 style parity)", () => {
    // Draft state: the finalize control is a text-link-style button in
    // the attribution slot, not a right-aligned primary Button.
    // The attribution slot (parent div) carries text-caption; the
    // button's ONLY distinguishing class from the finalized
    // attribution span is color — text-brass (draft, action) vs
    // text-status-success (finalized, muted). Color differentiates;
    // slot + typography are shared.
    const { container } = render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule({ state: "draft" })}
          deliveries={[makeDelivery()]}
        />
      </Harness>,
    )
    const btn = container.querySelector(
      '[data-slot="dispatch-day-finalize-btn"]',
    ) as HTMLElement
    expect(btn).toBeInTheDocument()
    // Action color — brass (draft = clickable).
    expect(btn.className).toMatch(/text-brass/)
    // Typography inherits from parent slot (text-caption). Assert the
    // parent carries it — the button shares the same visual weight as
    // the finalized attribution rendered in the same slot.
    const slot = btn.closest(".text-caption")
    expect(slot).not.toBeNull()
  })

  it("finalized schedule shows attribution + no Finalize button", () => {
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule({
            state: "finalized",
            finalized_at: "2026-04-23T20:00:00Z",
            finalized_by_user_id: "user-1",
          })}
          deliveries={[makeDelivery()]}
          finalizedByLabel="Finalized by Dana at 4:00 PM"
        />
      </Harness>,
    )
    expect(
      document.querySelector(
        '[data-slot="dispatch-day-finalized-attribution"]',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/finalized by dana at 4:00 PM/i),
    ).toBeInTheDocument()
    expect(
      document.querySelector('[data-slot="dispatch-day-finalize-btn"]'),
    ).toBeNull()
  })

  it("not_created schedule shows 'No schedule yet' affordance", () => {
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule({ state: "not_created" })}
          deliveries={[]}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-day-empty"]'),
    ).toBeInTheDocument()
    expect(
      document.querySelector(
        '[data-slot="dispatch-day-open-scheduling-btn"]',
      ),
    ).toBeInTheDocument()
  })
})


describe("MonitorDayColumn — driver lanes (Phase 3.3: all drivers always render)", () => {
  it("groups deliveries by assigned_driver_id with counts", () => {
    const deliveries = [
      makeDelivery({ assigned_driver_id: "driver-1" }),
      makeDelivery({ assigned_driver_id: "driver-1" }),
      makeDelivery({ assigned_driver_id: "driver-2" }),
    ]
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule()}
          deliveries={deliveries}
        />
      </Harness>,
    )
    const lanes = document.querySelectorAll(
      '[data-slot="dispatch-driver-lane"]',
    )
    // Phase 3.3: both drivers render even if only one had deliveries
    // (every active driver always gets a column). Here both have
    // deliveries so lane count is 2.
    expect(lanes.length).toBe(2)
    expect(screen.getByText("Dave Miller")).toBeInTheDocument()
    expect(screen.getByText("Tom Henderson")).toBeInTheDocument()
  })

  it("driver lanes are horizontal — kanban container uses flex-row overflow-x-auto", () => {
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule()}
          deliveries={[makeDelivery({ assigned_driver_id: "driver-1" })]}
        />
      </Harness>,
    )
    const kanban = document.querySelector(
      '[data-slot="dispatch-day-kanban"]',
    ) as HTMLElement
    expect(kanban).toBeInTheDocument()
    expect(kanban.className).toMatch(/flex-row/)
    expect(kanban.className).toMatch(/overflow-x-auto/)
  })

  it("surfaces unassigned lane when deliveries lack a driver", () => {
    const deliveries = [
      makeDelivery({ assigned_driver_id: null }),
      makeDelivery({ assigned_driver_id: "driver-1" }),
    ]
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule()}
          deliveries={deliveries}
        />
      </Harness>,
    )
    const lanes = document.querySelectorAll(
      '[data-slot="dispatch-driver-lane"]',
    )
    // Phase 3.3: unassigned + driver-1 + driver-2 (empty) = 3
    // lanes. Unassigned shows because there's an unassigned card;
    // driver-2 shows because Phase 3.3 always renders every driver.
    expect(lanes.length).toBe(3)
    expect(screen.getByText(/unassigned/i)).toBeInTheDocument()
  })

  it("empty driver columns render (Phase 3.3 — consistency across days)", () => {
    // Only driver-1 has a delivery; driver-2 is active but has 0.
    // Phase 3.2 skipped empty columns; Phase 3.3 renders them so the
    // driver-row baseline stays consistent across days.
    const deliveries = [
      makeDelivery({ assigned_driver_id: "driver-1" }),
    ]
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule()}
          deliveries={deliveries}
        />
      </Harness>,
    )
    const lanes = document.querySelectorAll(
      '[data-slot="dispatch-driver-lane"]',
    )
    expect(lanes.length).toBe(2)
    expect(screen.getByText("Dave Miller")).toBeInTheDocument()
    expect(screen.getByText("Tom Henderson")).toBeInTheDocument()

    // Tom Henderson's lane is present but marked empty.
    const tomLane = document.querySelector(
      '[data-lane$=":driver-2"]',
    ) as HTMLElement
    expect(tomLane).toBeInTheDocument()
    expect(tomLane.getAttribute("data-empty")).toBe("true")
    expect(
      tomLane.querySelector('[data-slot="dispatch-driver-lane-empty"]'),
    ).toBeInTheDocument()
  })

  it("renders empty state when no drivers AND no unassigned cards", () => {
    // Rare: no drivers in roster + no unassigned. Keeps
    // defense-in-depth empty state.
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          drivers={[]}
          schedule={makeSchedule({ state: "draft" })}
          deliveries={[]}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-day-empty"]'),
    ).toBeInTheDocument()
    expect(screen.getByText(/no deliveries scheduled/i)).toBeInTheDocument()
  })
})


describe("MonitorDayColumn — Phase 3.3 surface polish regression guards", () => {
  it("day section has no outer container chrome (no bg-surface-sunken, no border)", () => {
    const { container } = render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule({ state: "draft" })}
          deliveries={[makeDelivery()]}
        />
      </Harness>,
    )
    const section = container.querySelector(
      '[data-slot="dispatch-day-column"]',
    ) as HTMLElement
    expect(section).toBeInTheDocument()
    // Phase 3.3 removal: the day section no longer wraps itself in
    // a container. Cards + typography carry the composition.
    expect(section.className).not.toMatch(/bg-surface-sunken/)
    expect(section.className).not.toMatch(/shadow-level-/)
    expect(section.className).not.toMatch(/\bborder\b(?!-)/)
  })

  it("driver lane has no background container (Phase 3.3)", () => {
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule()}
          deliveries={[makeDelivery({ assigned_driver_id: "driver-1" })]}
        />
      </Harness>,
    )
    const lane = document.querySelector(
      '[data-slot="dispatch-driver-lane"]',
    ) as HTMLElement
    expect(lane).toBeInTheDocument()
    // Lane is typography + space; no box chrome in resting state.
    expect(lane.className).not.toMatch(/bg-surface-elevated/)
    expect(lane.className).not.toMatch(/bg-surface-sunken/)
    expect(lane.className).not.toMatch(/\brounded\b(?!-)/)
    expect(lane.className).not.toMatch(/\bborder\b(?!-)/)
  })
})


describe("MonitorDayColumn — ancillary expansion", () => {
  it("clicking +N badge reveals inline panel with ancillary family names", async () => {
    const user = userEvent.setup()
    const parent = makeDelivery({
      id: "parent-1",
      order_id: "so-1",
      assigned_driver_id: "driver-1",
    })
    const ancillary = makeDelivery({
      id: "anc-1",
      order_id: "so-1",
      scheduling_type: "ancillary",
      type_config: {
        family_name: "Patel",
        service_type: "ancillary_pickup",
      },
    })
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule()}
          deliveries={[parent]}
          ancillaryCounts={new Map([["parent-1", 1]])}
          ancillariesByParent={new Map([["parent-1", [ancillary]]])}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-expanded"]'),
    ).toBeNull()

    const badge = document.querySelector(
      '[data-slot="dispatch-ancillary-badge"]',
    ) as HTMLElement
    await user.click(badge)

    expect(
      document.querySelector('[data-slot="dispatch-ancillary-expanded"]'),
    ).toBeInTheDocument()
    expect(screen.getByText("Patel")).toBeInTheDocument()
  })
})


describe("MonitorDayColumn — finalize button", () => {
  it("click fires onFinalize with the date", async () => {
    const user = userEvent.setup()
    const onFinalize = vi.fn()
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule({ state: "draft" })}
          deliveries={[makeDelivery()]}
          onFinalize={onFinalize}
        />
      </Harness>,
    )
    await user.click(
      screen.getByRole("button", { name: /finalize schedule for tomorrow/i }),
    )
    expect(onFinalize).toHaveBeenCalledWith("2026-04-24")
  })
})
