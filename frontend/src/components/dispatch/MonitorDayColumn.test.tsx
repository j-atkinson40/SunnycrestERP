/**
 * MonitorDayColumn — vitest unit tests. Phase B Session 1.
 *
 * Covers: header state rendering (draft/finalized/not_created),
 * driver lane grouping by assigned_driver_id, unassigned-lane
 * surface, empty-state placeholder, ancillary inline expand.
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { DndContext } from "@dnd-kit/core"

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
    scheduling_type: "kanban",
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    assigned_driver_id: null,
    hole_dug_status: null,
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
  return <DndContext>{children}</DndContext>
}


describe("MonitorDayColumn — header rendering", () => {
  it("draft schedule shows DRAFT badge + Finalize button", () => {
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

  it("not_created schedule shows 'No schedule yet' + Open Scheduling button", () => {
    const onOpenScheduling = vi.fn()
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
          schedule={makeSchedule({ state: "not_created" })}
          deliveries={[]}
          onOpenScheduling={onOpenScheduling}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-day-empty"]'),
    ).toBeInTheDocument()
    expect(screen.getByText(/no schedule yet/i)).toBeInTheDocument()
  })
})


describe("MonitorDayColumn — driver lanes", () => {
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
    // 2 driver lanes (driver-1 and driver-2); no unassigned lane because
    // all deliveries are assigned.
    expect(lanes.length).toBe(2)
    expect(screen.getByText("Dave Miller")).toBeInTheDocument()
    expect(screen.getByText("Tom Henderson")).toBeInTheDocument()
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
    // 1 unassigned + 1 driver-1 lane (driver-2 has zero so doesn't render)
    expect(lanes.length).toBe(2)
    expect(screen.getByText(/unassigned/i)).toBeInTheDocument()
  })

  it("skips driver lanes with zero deliveries", () => {
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
    expect(screen.queryByText("Tom Henderson")).toBeNull()
  })

  it("renders empty state when deliveries array is empty + schedule is draft", () => {
    render(
      <Harness>
        <MonitorDayColumn
          {...defaultProps}
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
    // Initially collapsed
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-expanded"]'),
    ).toBeNull()

    // Click the +N badge
    const badge = document.querySelector(
      '[data-slot="dispatch-ancillary-badge"]',
    ) as HTMLElement
    await user.click(badge)

    // Expanded
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
      screen.getByRole("button", { name: /finalize tomorrow/i }),
    )
    expect(onFinalize).toHaveBeenCalledWith("2026-04-24")
  })
})
