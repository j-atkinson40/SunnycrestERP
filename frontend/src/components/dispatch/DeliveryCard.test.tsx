/**
 * DeliveryCard — vitest unit tests. Phase B Session 1 Phase 3.1+3.2.
 *
 * Covers visual-state rendering (draft/finalized border, no
 * service-type tints post-3.1), hole-dug three-state cycle (no null),
 * ancillary badge toggle, icon+tooltip compaction row (family / note
 * / chat / section), primary text hierarchy (FH headline, cemetery ·
 * city, service-time with ETA, vault · equipment), and body
 * click-to-edit.
 */

import { render } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { DndContext } from "@dnd-kit/core"
import { TooltipProvider } from "@/components/ui/tooltip"

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
    completed_at: null,
    scheduling_type: "kanban",
    ancillary_fulfillment_status: null,
    direct_ship_status: null,
    assigned_driver_id: "driver-1",
    hole_dug_status: "unknown",
    type_config: {
      family_name: "Fitzgerald",
      cemetery_name: "St. Joseph's Cemetery",
      cemetery_city: "Auburn",
      cemetery_section: "Sec 14, Lot 42B",
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
  // TooltipProvider mirrors the app-root mount (for the icon+tooltip
  // compaction row). DndContext required by useDraggable.
  return (
    <TooltipProvider delay={0}>
      <DndContext>{children}</DndContext>
    </TooltipProvider>
  )
}


// ── Tests ─────────────────────────────────────────────────────────────


describe("nextHoleDugStatus three-state cycle (Phase 3.1)", () => {
  it("cycles unknown → yes → no → unknown (no null state)", () => {
    expect(nextHoleDugStatus("unknown")).toBe("yes")
    expect(nextHoleDugStatus("yes")).toBe("no")
    expect(nextHoleDugStatus("no")).toBe("unknown")
  })
})


describe("DeliveryCard — primary text hierarchy (Phase 3.1)", () => {
  it("funeral home is the headline", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{ ...base, type_config: { ...base.type_config } }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const fh = document.querySelector('[data-slot="dispatch-card-fh"]')
    expect(fh).toBeInTheDocument()
    expect(fh?.textContent).toBe("Johnson Funeral Home")
  })

  it("cemetery line shows name · city", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    const cem = document.querySelector('[data-slot="dispatch-card-cemetery"]')
    expect(cem).toBeInTheDocument()
    expect(cem?.textContent).toMatch(/St\. Joseph's Cemetery/)
    expect(cem?.textContent).toMatch(/Auburn/)
  })

  it("service time line — graveside shows only time + location, no ETA", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    const line = document.querySelector('[data-slot="dispatch-card-timeline"]')
    expect(line).toBeInTheDocument()
    expect(line?.textContent).toMatch(/10:00/)
    expect(line?.textContent).toMatch(/Graveside/)
    expect(line?.textContent).not.toMatch(/ETA/)
  })

  it("service time line — church shows '11:00 Church · ETA 12:00' order", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              service_type: "church",
              service_time: "11:00",
              eta: "12:00",
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const line = document.querySelector('[data-slot="dispatch-card-timeline"]')
    expect(line?.textContent).toMatch(/11:00/)
    expect(line?.textContent).toMatch(/Church/)
    expect(line?.textContent).toMatch(/ETA 12:00/)
    // Service time MUST precede ETA in the rendered string.
    const txt = line?.textContent ?? ""
    const serviceIdx = txt.indexOf("11:00")
    const etaIdx = txt.indexOf("ETA")
    expect(serviceIdx).toBeGreaterThanOrEqual(0)
    expect(etaIdx).toBeGreaterThan(serviceIdx)
  })

  it("service time line — funeral_home shows 'time Funeral Home · ETA Y'", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              service_type: "funeral_home",
              service_time: "14:00",
              eta: "15:30",
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const line = document.querySelector('[data-slot="dispatch-card-timeline"]')
    expect(line?.textContent).toMatch(/14:00/)
    expect(line?.textContent).toMatch(/Funeral Home/)
    expect(line?.textContent).toMatch(/ETA 15:30/)
  })

  it("product line shows vault type · equipment hint", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    const prod = document.querySelector('[data-slot="dispatch-card-product"]')
    expect(prod?.textContent).toMatch(/Monticello/)
    expect(prod?.textContent).toMatch(/Graveside setup/)
  })
})


describe("DeliveryCard — no service-type tint (Phase 3.1 removal)", () => {
  it("graveside card does NOT carry bg-status-success-muted", () => {
    const { container } = render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).not.toMatch(/bg-status-success-muted/)
    expect(card?.className).toMatch(/bg-surface-elevated/)
  })

  it("church card does NOT carry bg-status-warning-muted", () => {
    const base = makeDelivery()
    const { container } = render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: { ...base.type_config, service_type: "church" },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const card = container.querySelector('[data-slot="dispatch-delivery-card"]')
    expect(card?.className).not.toMatch(/bg-status-warning-muted/)
    expect(card?.className).toMatch(/bg-surface-elevated/)
  })
})


describe("DeliveryCard — border state", () => {
  it("draft schedule → dashed border", () => {
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
})


describe("DeliveryCard — hole-dug badge (three-state, non-nullable)", () => {
  it("status=unknown renders by default (no null state)", () => {
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "unknown" })}
          scheduleFinalized={false}
          onCycleHoleDug={() => {}}
        />
      </Harness>,
    )
    const badge = document.querySelector(
      '[data-slot="dispatch-hole-dug-badge"]',
    ) as HTMLElement
    expect(badge).toBeInTheDocument()
    expect(badge.getAttribute("data-status")).toBe("unknown")
  })

  it("click on unknown → cycles to yes", async () => {
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
    expect(onCycle.mock.calls[0][1]).toBe("yes")
  })

  it("click on no → cycles back to unknown (not null)", async () => {
    const user = userEvent.setup()
    const onCycle = vi.fn()
    render(
      <Harness>
        <DeliveryCard
          delivery={makeDelivery({ hole_dug_status: "no" })}
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
    expect(onCycle.mock.calls[0][1]).toBe("unknown")
  })
})


describe("DeliveryCard — icon + tooltip compaction row (Phase 3.2)", () => {
  it("family icon renders when family_name is present", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-family"]'),
    ).toBeInTheDocument()
  })

  it("section icon renders when cemetery_section is present", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-section"]'),
    ).toBeInTheDocument()
  })

  it("section icon hidden when cemetery_section is empty", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: { ...base.type_config, cemetery_section: null },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-section"]'),
    ).toBeNull()
  })

  it("note icon renders only when driver_note non-empty", () => {
    const base = makeDelivery()
    const { rerender } = render(
      <Harness>
        <DeliveryCard delivery={base} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-note"]'),
    ).toBeNull()

    rerender(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: {
              ...base.type_config,
              driver_note: "FH said procession may run long",
            },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-note"]'),
    ).toBeInTheDocument()
  })

  it("chat icon + badge render when chat_activity_count > 0", () => {
    const base = makeDelivery()
    render(
      <Harness>
        <DeliveryCard
          delivery={{
            ...base,
            type_config: { ...base.type_config, chat_activity_count: 3 },
          }}
          scheduleFinalized={false}
        />
      </Harness>,
    )
    const icon = document.querySelector('[data-slot="dispatch-icon-chat"]')
    expect(icon).toBeInTheDocument()
    const badge = document.querySelector(
      '[data-slot="dispatch-icon-chat-badge"]',
    )
    expect(badge?.textContent).toBe("3")
  })

  it("chat icon hidden when chat_activity_count is 0", () => {
    render(
      <Harness>
        <DeliveryCard delivery={makeDelivery()} scheduleFinalized={false} />
      </Harness>,
    )
    expect(
      document.querySelector('[data-slot="dispatch-icon-chat"]'),
    ).toBeNull()
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
