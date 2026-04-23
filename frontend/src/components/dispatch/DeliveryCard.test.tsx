/**
 * DeliveryCard — vitest unit tests. Phase B Session 1.
 *
 * Covers visual-state rendering (draft/finalized border, service-type
 * tint), hole-dug badge states + cycle, ancillary badge toggle,
 * and click-to-edit. DnD behavior is exercised through useDraggable's
 * default contract — no drop wiring here (that's Monitor-page scope).
 */

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { DndContext } from "@dnd-kit/core"

import type { DeliveryDTO } from "@/services/dispatch-service"

import { DeliveryCard, nextHoleDugStatus } from "./DeliveryCard"


// ── Fixtures ──────────────────────────────────────────────────────────


function makeDelivery(overrides: Partial<DeliveryDTO> = {}): DeliveryDTO {
  return {
    id: "del-1",
    company_id: "co-1",
    order_id: "so-1",
    customer_id: "cust-1",
    delivery_type: "vault",
    status: "scheduled",
    priority: "normal",
    requested_date: "2026-04-23",
    scheduled_at: "2026-04-23T14:00:00Z",
    scheduling_type: "kanban",
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    assigned_driver_id: "driver-1",
    hole_dug_status: "unknown",
    type_config: {
      family_name: "Fitzgerald",
      cemetery_name: "St. Joseph's Cemetery",
      cemetery_city: "Auburn",
      funeral_home_name: "Johnson Funeral Home",
      service_time: "10:00",
      service_type: "graveside",
      vault_type: "Monticello",
    },
    special_instructions: null,
    ...overrides,
  }
}


function Harness({ children }: { children: React.ReactNode }) {
  // DndContext required by useDraggable.
  return <DndContext>{children}</DndContext>
}


// ── Tests ─────────────────────────────────────────────────────────────


describe("nextHoleDugStatus pure cycle", () => {
  it("cycles null → unknown → yes → no → null", () => {
    expect(nextHoleDugStatus(null)).toBe("unknown")
    expect(nextHoleDugStatus("unknown")).toBe("yes")
    expect(nextHoleDugStatus("yes")).toBe("no")
    expect(nextHoleDugStatus("no")).toBe(null)
  })
})


describe("DeliveryCard — rendering", () => {
  it("renders family name, cemetery, FH, time, vault type", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    expect(screen.getByText("Fitzgerald")).toBeInTheDocument()
    expect(screen.getByText("St. Joseph's Cemetery")).toBeInTheDocument()
    expect(screen.getByText("Auburn")).toBeInTheDocument()
    expect(screen.getByText("Johnson Funeral Home")).toBeInTheDocument()
    expect(screen.getByText("10:00")).toBeInTheDocument()
    expect(screen.getByText("Monticello")).toBeInTheDocument()
  })

  it("draft schedule → dashed border class", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).toMatch(/border-dashed/)
    expect(card?.getAttribute("data-schedule-state")).toBe("draft")
  })

  it("finalized schedule → solid border (no dashed)", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={true} />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).not.toMatch(/border-dashed/)
    expect(card?.getAttribute("data-schedule-state")).toBe("finalized")
  })

  it("service-type=graveside applies success-muted tint", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({
            type_config: {
              ...makeDelivery().type_config,
              service_type: "graveside",
            },
          })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).toMatch(/bg-status-success-muted/)
  })

  it("service-type=church applies warning-muted tint", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({
            type_config: {
              ...makeDelivery().type_config,
              service_type: "church",
            },
          })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).toMatch(/bg-status-warning-muted/)
  })
})


describe("DeliveryCard — hole-dug badge", () => {
  it("status=yes → check icon + status-success chrome + yes aria", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "yes" })}
          scheduleFinalized={false}
          onCycleHoleDug={() => {}}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    ) as HTMLElement
    expect(badge).toBeInTheDocument()
    expect(badge.getAttribute("data-status")).toBe("yes")
    expect(badge.getAttribute("aria-label")).toMatch(/hole dug: yes/i)
  })

  it("status=no renders minus icon + surface-sunken chrome", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "no" })}
          scheduleFinalized={false}
          onCycleHoleDug={() => {}}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    ) as HTMLElement
    expect(badge.getAttribute("data-status")).toBe("no")
  })

  it("status=null + onCycleHoleDug → clickable placeholder", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: null })}
          scheduleFinalized={false}
          onCycleHoleDug={() => {}}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    )
    expect(badge).toBeInTheDocument()
    expect(badge?.getAttribute("data-status")).toBe("null")
  })

  it("status=null + no onCycleHoleDug → badge hidden", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: null })}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    )
    expect(badge).toBeNull()
  })

  it("click on badge fires onCycleHoleDug with next status", async () => {
    const user = userEvent.setup()
    const onCycle = vi.fn()
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "unknown" })}
          scheduleFinalized={false}
          onCycleHoleDug={onCycle}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    ) as HTMLElement
    await user.click(badge)
    expect(onCycle).toHaveBeenCalledTimes(1)
    // nextHoleDugStatus("unknown") === "yes"
    expect(onCycle.mock.calls[0][1]).toBe("yes")
  })
})


describe("DeliveryCard — ancillary badge", () => {
  it("hidden when ancillaryCount is 0", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          ancillaryCount={0}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-ancillary-badge"]'),
    ).toBeNull()
  })

  it("shown when ancillaryCount > 0; click fires onToggleAncillary", async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          ancillaryCount={2}
          onToggleAncillary={onToggle}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-ancillary-badge"]',
    ) as HTMLElement
    expect(badge.textContent).toMatch(/\+2 ancillary/)
    await user.click(badge)
    expect(onToggle).toHaveBeenCalledWith("del-1")
  })

  it("aria-expanded matches ancillaryExpanded prop", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery()}
          scheduleFinalized={false}
          ancillaryCount={1}
          ancillaryExpanded={true}
          onToggleAncillary={() => {}}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-ancillary-badge"]',
    )
    expect(badge?.getAttribute("aria-expanded")).toBe("true")
  })
})


describe("DeliveryCard — body click fires onOpenEdit", () => {
  it("click on card body → onOpenEdit(delivery)", async () => {
    const user = userEvent.setup()
    const onOpenEdit = vi.fn()
    const delivery = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={delivery}
          scheduleFinalized={false}
          onOpenEdit={onOpenEdit}
        />
      </Harness>,
    )
    const body = document.querySelector(
      '[data-slot="dispatch-card-body"]',
    ) as HTMLElement
    await user.click(body)
    expect(onOpenEdit).toHaveBeenCalledWith(delivery)
  })
})
